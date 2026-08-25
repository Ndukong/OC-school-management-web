from decimal import Decimal

from core.models import (
    AcademicTerm,
    ClassCouncilRemark,
    ClassSubject,
    School,
    SchoolClass,
    Student,
    SubjectAverage,
    TermResult,
)
from core.utils.grading import PASS_MARK, compute_promotion_decision, compute_term_total
from core.utils.reports import BaseReport


def _term_results_by_class(school: School, term: AcademicTerm) -> dict[int, list]:
    """Map class_id -> list of (student, average) for students with a mark."""
    results = list(
        TermResult.objects.filter(
            academic_term=term,
            student__enrollments__school_class__school=school,
        )
        .select_related("student")
        .prefetch_related("student__enrollments__school_class")
        .distinct()
    )
    by_class: dict[int, list] = {}
    for r in results:
        if not r.average or r.average <= 0:
            continue
        for e in r.student.enrollments.all():
            if e.academic_term_id == term.pk and e.school_class.school_id == school.pk:
                by_class.setdefault(e.school_class_id, []).append(
                    (r.student, r.average)
                )
                break
    return by_class


def _annual_results_by_class(
    school: School, terms: list[AcademicTerm]
) -> tuple[dict[int, list], dict[int, list]]:
    """Return (on_roll, abandoned) mappings class_id -> student rows.

    on_roll: list of (student, annual_avg) — students who sat at least one
             subject in the third term. Annual average is coefficient-weighted
             across the subjects they have marks in.
    abandoned: list of Student — enrolled but with no mark in the third term
             (i.e. had marks in earlier terms but none in the final term).
    """
    term_ids = {t.pk for t in terms}
    third_term = max(terms, key=lambda t: t.term_number) if terms else None

    averages = SubjectAverage.objects.filter(
        academic_term__in=terms,
        student__enrollments__school_class__school=school,
    ).select_related("student")

    # student -> {subject_id: {term_id: average}}
    by_student_subject: dict[int, dict[int, dict[int, Decimal]]] = {}
    by_class_of_student: dict[int, int] = {}
    for sa in averages:
        entry = by_student_subject.setdefault(sa.student_id, {})
        entry.setdefault(sa.subject_id, {})[sa.academic_term_id] = sa.average
        if not by_class_of_student.get(sa.student_id):
            for e in sa.student.enrollments.all():
                if e.academic_term_id in term_ids:
                    by_class_of_student[sa.student_id] = e.school_class_id
                    break

    # class_id -> {subject_id: coefficient}
    coef_map: dict[int, dict[int, int]] = {}
    for cs in ClassSubject.objects.filter(school_class__school=school):
        coef_map.setdefault(cs.school_class_id, {})[cs.subject_id] = cs.coefficient

    on_roll: dict[int, list] = {}
    abandoned: dict[int, list] = {}
    student_cache: dict[int, Student] = {}

    for student_id, subjects in by_student_subject.items():
        class_id = by_class_of_student.get(student_id)
        if class_id is None:
            continue
        student = student_cache.get(student_id)
        if student is None:
            student = Student.objects.filter(pk=student_id).first()
            if student is None:
                continue
            student_cache[student_id] = student

        # On roll requires participation in the third term
        has_third = False
        if third_term is not None:
            for term_avgs in subjects.values():
                if term_avgs.get(third_term.pk) is not None:
                    has_third = True
                    break
        if not has_third:
            abandoned.setdefault(class_id, []).append(student)
            continue

        # Annual average = coefficient-weighted mean of subject annual averages
        coeffs = coef_map.get(class_id, {})
        weighted = []
        for subject_id, term_avgs in subjects.items():
            present = [v for v in term_avgs.values() if v is not None and v > 0]
            if not present:
                continue
            subject_avg = (sum(present) / Decimal(len(present))).quantize(Decimal("0.01"))
            coef = coeffs.get(subject_id, 1)
            weighted.append((subject_avg, coef))

        if not weighted:
            abandoned.setdefault(class_id, []).append(student)
            continue

        _, _, annual_avg = compute_term_total(weighted)
        on_roll.setdefault(class_id, []).append((student, annual_avg))

    return on_roll, abandoned


def _pass_remark(pct: Decimal) -> str:
    """Qualitative remark for a class based on % pass."""
    if pct >= Decimal(90):
        return "Excellent"
    if pct >= Decimal(80):
        return "Very good"
    if pct >= Decimal(70):
        return "Good"
    if pct >= Decimal(60):
        return "Fairly good"
    if pct >= Decimal(50):
        return "Average"
    if pct >= Decimal(40):
        return "Below average"
    return "Weak"


def _class_stats(rows: list) -> dict:
    """Compute on-roll / sat / passed / failed / % pass / average for one class."""
    male = [r for r in rows if r[0].sex == "M"]
    female = [r for r in rows if r[0].sex == "F"]
    on_roll_m = len(male)
    on_roll_f = len(female)
    passed_m = len([r for r in male if r[1] >= PASS_MARK])
    passed_f = len([r for r in female if r[1] >= PASS_MARK])
    sat_m = on_roll_m
    sat_f = on_roll_f
    sat_t = on_roll_m + on_roll_f
    passed_t = passed_m + passed_f
    failed_m = on_roll_m - passed_m
    failed_f = on_roll_f - passed_f
    failed_t = sat_t - passed_t
    pct_pass = (
        (Decimal(passed_t) / Decimal(sat_t) * Decimal(100)).quantize(Decimal("0.1"))
        if sat_t else Decimal(0)
    )
    class_average = (
        (sum(r[1] for r in rows) / Decimal(len(rows))).quantize(Decimal("0.01"))
        if rows else Decimal(0)
    )
    return {
        "on_roll_m": on_roll_m,
        "on_roll_f": on_roll_f,
        "on_roll_t": on_roll_m + on_roll_f,
        "sat_m": sat_m,
        "sat_f": sat_f,
        "sat_t": sat_t,
        "passed_m": passed_m,
        "passed_f": passed_f,
        "passed_t": passed_t,
        "failed_m": failed_m,
        "failed_f": failed_f,
        "failed_t": failed_t,
        "pct_pass": pct_pass,
        "class_average": class_average,
        "remark": _pass_remark(pct_pass),
    }


def _totals(classes_data: list) -> dict:
    stats = _class_stats([])
    keys = [
        "on_roll_m", "on_roll_f", "on_roll_t",
        "sat_m", "sat_f", "sat_t",
        "passed_m", "passed_f", "passed_t",
        "failed_m", "failed_f", "failed_t",
    ]
    for key in keys:
        stats[key] = sum(c["stats"][key] for c in classes_data)
    sat_t = stats["sat_t"]
    stats["pct_pass"] = (
        (Decimal(stats["passed_t"]) / Decimal(sat_t) * Decimal(100)).quantize(Decimal("0.1"))
        if sat_t else Decimal(0)
    )
    stats["remark"] = _pass_remark(stats["pct_pass"])
    weights = [c["stats"]["sat_t"] for c in classes_data]
    total_w = sum(weights)
    stats["class_average"] = (
        (
            sum(
                c["stats"]["class_average"] * Decimal(w)
                for c, w in zip(classes_data, weights)
            )
            / Decimal(total_w)
        ).quantize(Decimal("0.01"))
        if total_w else Decimal(0)
    )
    return stats


def _annual_class_stats(
    rows: list, promotion_mark: Decimal, dismissal_mark: Decimal | None
) -> dict:
    """Compute annual on-roll / sat / promoted / repeat / dismissed / abandoned."""
    male = [r for r in rows if r[0].sex == "M"]
    female = [r for r in rows if r[0].sex == "F"]
    on_roll_m = len(male)
    on_roll_f = len(female)
    on_roll_t = on_roll_m + on_roll_f

    def decision_count(students: list) -> tuple[int, int, int]:
        promoted = repeat = dismissed = 0
        for _, avg in students:
            decision = compute_promotion_decision(
                avg, promotion_mark, dismissal_mark=dismissal_mark
            )
            if decision == "PROMOTED" or decision == "PROMOTED BY CLEMENCY OF COUNCIL":
                promoted += 1
            elif decision == "DISMISSED":
                dismissed += 1
            else:
                repeat += 1
        return promoted, repeat, dismissed

    promoted_m, repeat_m, dismissed_m = decision_count(male)
    promoted_f, repeat_f, dismissed_f = decision_count(female)
    promoted_t = promoted_m + promoted_f
    pct_promoted = (
        (Decimal(promoted_t) / Decimal(on_roll_t) * Decimal(100)).quantize(Decimal("0.1"))
        if on_roll_t else Decimal(0)
    )
    return {
        "on_roll_m": on_roll_m,
        "on_roll_f": on_roll_f,
        "on_roll_t": on_roll_t,
        "sat_m": on_roll_m,
        "sat_f": on_roll_f,
        "sat_t": on_roll_t,
        "promoted_m": promoted_m,
        "promoted_f": promoted_f,
        "promoted_t": promoted_t,
        "pct_promoted": pct_promoted,
        "repeat_m": repeat_m,
        "repeat_f": repeat_f,
        "repeat_t": repeat_m + repeat_f,
        "dismissed_m": dismissed_m,
        "dismissed_f": dismissed_f,
        "dismissed_t": dismissed_m + dismissed_f,
        "abandoned_m": 0,
        "abandoned_f": 0,
        "abandoned_t": 0,
    }


def _annual_totals(classes_data: list) -> dict:
    stats = _annual_class_stats([], Decimal(10), None)
    keys = [
        "on_roll_m", "on_roll_f", "on_roll_t",
        "sat_m", "sat_f", "sat_t",
        "promoted_m", "promoted_f", "promoted_t",
        "repeat_m", "repeat_f", "repeat_t",
        "dismissed_m", "dismissed_f", "dismissed_t",
        "abandoned_m", "abandoned_f", "abandoned_t",
    ]
    for key in keys:
        stats[key] = sum(c["stats"][key] for c in classes_data)
    on_roll_t = stats["on_roll_t"]
    stats["pct_promoted"] = (
        (Decimal(stats["promoted_t"]) / Decimal(on_roll_t) * Decimal(100)).quantize(Decimal("0.1"))
        if on_roll_t else Decimal(0)
    )
    return stats


class ClassCouncilReport(BaseReport):
    """School-wide class council report for one academic term."""

    template_name = "reports/class_council.html"
    css_files = ["reports/css/report.css"]

    def __init__(self, term: AcademicTerm, school: School):
        self.term = term
        self.school = school

    def get_context_data(self) -> dict:
        classes = list(
            SchoolClass.objects.filter(school=self.school).order_by("sort_order")
        )
        by_class = _term_results_by_class(self.school, self.term)

        remarks = {
            r.school_class_id: r
            for r in ClassCouncilRemark.objects.filter(
                school=self.school, academic_term=self.term
            )
        }

        classes_data = []
        for cls in classes:
            remark = remarks.get(cls.pk)
            if remark and remark.motif:
                classes_data.append({
                    "school_class": cls,
                    "withheld": True,
                    "motif": remark.motif,
                    "stats": None,
                })
                continue
            rows = by_class.get(cls.pk, [])
            if not rows:
                classes_data.append({
                    "school_class": cls,
                    "withheld": True,
                    "motif": remark.motif if remark else "",
                    "stats": None,
                })
                continue
            classes_data.append({
                "school_class": cls,
                "withheld": False,
                "motif": "",
                "stats": _class_stats(rows),
            })

        totals = _totals([c for c in classes_data if c["stats"]])

        return {
            "school": self.school,
            "term": self.term,
            "classes_data": classes_data,
            "totals": totals,
            "is_annual": False,
        }

    def filename(self) -> str:
        return (
            f"class_council_{self.school.matricule}_"
            f"T{self.term.term_number}_{self.term.year_start}_{self.term.year_end}.pdf"
        )


class AnnualClassCouncilReport(BaseReport):
    """School-wide class council report for an academic year (terms 1-3)."""

    template_name = "reports/class_council.html"
    css_files = ["reports/css/report.css"]

    def __init__(self, year_start: int, year_end: int, school: School):
        self.year_start = year_start
        self.year_end = year_end
        self.school = school

    def get_context_data(self) -> dict:
        terms = list(
            AcademicTerm.objects.filter(
                school=self.school, year_start=self.year_start, year_end=self.year_end
            ).order_by("term_number")
        )
        classes = list(
            SchoolClass.objects.filter(school=self.school).order_by("sort_order")
        )
        on_roll_by_class, abandoned_by_class = _annual_results_by_class(
            self.school, terms
        )

        remarks = {
            r.school_class_id: r
            for r in ClassCouncilRemark.objects.filter(
                school=self.school,
                year_start=self.year_start,
                year_end=self.year_end,
            )
        }

        classes_data = []
        for cls in classes:
            remark = remarks.get(cls.pk)
            if remark and remark.motif:
                classes_data.append({
                    "school_class": cls,
                    "withheld": True,
                    "motif": remark.motif,
                    "stats": None,
                })
                continue
            rows = on_roll_by_class.get(cls.pk, [])
            abandoned_students = abandoned_by_class.get(cls.pk, [])
            if not rows and not abandoned_students:
                classes_data.append({
                    "school_class": cls,
                    "withheld": True,
                    "motif": remark.motif if remark else "",
                    "stats": None,
                })
                continue

            promotion_mark = (
                Decimal(str(cls.promotion_mark)) if cls.promotion_mark else Decimal(10)
            )
            dismissal_mark = (
                Decimal(str(cls.dismissal_mark)) if cls.dismissal_mark else None
            )
            stats = _annual_class_stats(rows, promotion_mark, dismissal_mark)
            stats["abandoned_m"] = sum(1 for s in abandoned_students if s.sex == "M")
            stats["abandoned_f"] = sum(1 for s in abandoned_students if s.sex == "F")
            stats["abandoned_t"] = stats["abandoned_m"] + stats["abandoned_f"]

            classes_data.append({
                "school_class": cls,
                "withheld": False,
                "motif": "",
                "stats": stats,
            })

        totals = _annual_totals([c for c in classes_data if c["stats"]])

        return {
            "school": self.school,
            "terms": terms,
            "term": terms[0] if terms else None,
            "classes_data": classes_data,
            "totals": totals,
            "year_start": self.year_start,
            "year_end": self.year_end,
            "is_annual": True,
        }

    def filename(self) -> str:
        return (
            f"class_council_annual_{self.school.matricule}_"
            f"{self.year_start}_{self.year_end}.pdf"
        )
