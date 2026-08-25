from decimal import Decimal

from core.models import (
    AcademicTerm,
    ClassSubject,
    SchoolClass,
    Student,
    SubjectAverage,
    TeacherAssignment,
)
from core.utils.grading import (
    compute_promotion_decision,
    is_pass,
)
from core.utils.reports import BaseReport


def _ordinal(n: int) -> str:
    if n % 100 in (11, 12, 13):
        return f"{n}th"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _full_remark(average: Decimal | None, promotion_mark: Decimal) -> str:
    """Full-text remark: Passed/Failed for term sheets, Promoted/Repeat for annual."""
    if average is None:
        return ""
    if is_pass(average):
        return "Passed"
    return "Failed"


def _annual_remark(
    average: Decimal | None, promotion_mark: Decimal, dismissal_mark: Decimal | None = None
) -> str:
    if average is None:
        return ""
    decision = compute_promotion_decision(
        average, promotion_mark, dismissal_mark=dismissal_mark
    )
    if decision == "PROMOTED BY CLEMENCY OF COUNCIL":
        return "Promoted by Clemency"
    return decision.title()


class MarkSheet(BaseReport):
    template_name = "reports/mark_sheet.html"
    css_files = ["reports/css/report.css"]

    def __init__(self, school_class: SchoolClass, term: AcademicTerm, school):
        self.school_class = school_class
        self.term = term
        self.school = school

    def get_context_data(self) -> dict:
        students = list(
            Student.objects.filter(
                enrollments__school_class=self.school_class,
                enrollments__academic_term=self.term,
                is_active=True,
            ).order_by("first_name", "other_names")
        )

        class_subjects = list(
            ClassSubject.objects.filter(
                school_class=self.school_class
            ).select_related("subject").order_by("sort_order")
        )

        subject_ids = [cs.subject_id for cs in class_subjects]

        # Fetch all subject averages for this class in one query
        averages = SubjectAverage.objects.filter(
            student__in=students,
            subject_id__in=subject_ids,
            academic_term=self.term,
        )

        avg_map: dict[tuple[int, int], Decimal] = {}
        for sa in averages:
            avg_map[(sa.student_id, sa.subject_id)] = sa.average

        rows = []
        total_male = 0
        total_female = 0
        all_averages = []

        for student in students:
            weighted_scores = []
            row_avgs = []
            for cs in class_subjects:
                avg = avg_map.get((student.pk, cs.subject_id))
                if avg is not None:
                    weighted = avg * Decimal(cs.coefficient)
                    weighted_scores.append({
                        "score": weighted,
                        "coef": cs.coefficient,
                        "fail": avg < Decimal(10),
                    })
                    row_avgs.append(avg)
                else:
                    weighted_scores.append(None)
                    row_avgs.append(None)

            # Count coef only for subjects with a mark
            total_coef = sum(
                cs.coefficient for i, cs in enumerate(class_subjects)
                if row_avgs[i] is not None
            )
            total_score = sum(
                (ws["score"] for ws in weighted_scores if ws is not None),
                Decimal(0),
            )
            average = (
                (total_score / Decimal(total_coef)).quantize(Decimal("0.01"))
                if total_coef > 0 else Decimal(0)
            )
            all_averages.append(average)

            has_marks = total_coef > 0
            if not has_marks:
                # Skip students with no marks entirely.
                continue

            if student.sex == "M":
                total_male += 1
            else:
                total_female += 1

            rows.append({
                "student": student,
                "weighted_scores": weighted_scores,
                "total_coef": total_coef,
                "total_score": total_score.quantize(Decimal("0.01")),
                "average": average,
                "has_marks": True,
                "remark": _full_remark(average, Decimal(0)),
            })

        # Compute ranks (nominal)
        sorted_rows = sorted(
            rows,
            key=lambda r: r["average"] if r["average"] is not None else Decimal(0),
            reverse=True,
        )
        rank_map = {}
        current_rank = 1
        for i, r in enumerate(sorted_rows):
            if i > 0 and r["average"] < sorted_rows[i - 1]["average"]:
                current_rank = i + 1
            rank_map[r["student"].pk] = _ordinal(current_rank)

        for r in rows:
            r["rank"] = rank_map.get(r["student"].pk, "")

        # Class stats
        num_sat = len(rows)
        num_passed = len([r for r in rows if r["average"] >= Decimal(10)])
        class_avg = (
            (sum(all_averages) / Decimal(len(all_averages))).quantize(Decimal("0.01"))
            if all_averages else Decimal(0)
        )
        success_rate = (
            (Decimal(num_passed) / Decimal(num_sat) * Decimal(100)).quantize(Decimal("0.1"))
            if num_sat > 0 else Decimal(0)
        )

        class_master = ""
        class_master_signature = ""
        cm = TeacherAssignment.objects.filter(
            school_class=self.school_class, is_class_master=True, is_active=True,
        ).select_related("teacher").first()
        if cm:
            class_master = f"{cm.teacher.first_name} {cm.teacher.last_name}"
            class_master_signature = cm.teacher.signature.url if cm.teacher.signature else ""

        return {
            "school": self.school,
            "school_class": self.school_class,
            "term": self.term,
            "class_subjects": class_subjects,
            "rows": rows,
            "enrolment_m": total_male,
            "enrolment_f": total_female,
            "enrolment_total": total_male + total_female,
            "num_sat": num_sat,
            "num_passed": num_passed,
            "class_average": class_avg,
            "success_rate": success_rate,
            "class_master": class_master,
            "class_master_signature": class_master_signature,
            "is_annual": False,
        }

    def filename(self) -> str:
        return (
            f"mark_sheet_{self.school_class.code}_"
            f"T{self.term.term_number}_{self.term.year_start}_{self.term.year_end}.pdf"
        )


class AnnualMarkSheet(BaseReport):
    template_name = "reports/mark_sheet.html"
    css_files = ["reports/css/report.css"]

    def __init__(self, school_class: SchoolClass, year_start: int, year_end: int, school):
        self.school_class = school_class
        self.year_start = year_start
        self.year_end = year_end
        self.school = school

    def get_context_data(self) -> dict:
        terms = list(
            AcademicTerm.objects.filter(
                school=self.school,
                year_start=self.year_start,
                year_end=self.year_end,
            ).order_by("term_number")
        )

        students = list(
            Student.objects.filter(
                enrollments__school_class=self.school_class,
                enrollments__academic_term__in=terms,
                is_active=True,
            ).distinct().order_by("first_name", "other_names")
        )

        class_subjects = list(
            ClassSubject.objects.filter(
                school_class=self.school_class
            ).select_related("subject").order_by("sort_order")
        )

        # For annual, average = mean of term averages
        averages = SubjectAverage.objects.filter(
            student__in=students,
            subject_id__in=[cs.subject_id for cs in class_subjects],
            academic_term__in=terms,
        )

        avg_map: dict[tuple[int, int, int], Decimal] = {}
        for sa in averages:
            avg_map[(sa.student_id, sa.subject_id, sa.academic_term_id)] = sa.average

        promotion_mark = (
            Decimal(str(self.school_class.promotion_mark))
            if self.school_class.promotion_mark
            else Decimal(10)
        )
        dismissal_mark = (
            Decimal(str(self.school_class.dismissal_mark))
            if self.school_class.dismissal_mark
            else None
        )

        rows = []
        for student in students:
            weighted_scores = []
            for cs in class_subjects:
                term_avgs = [
                    avg_map.get((student.pk, cs.subject_id, t.pk))
                    for t in terms
                ]
                present = [a for a in term_avgs if a is not None]
                annual_avg = (
                    (sum(present) / Decimal(len(present))).quantize(Decimal("0.01"))
                    if present else None
                )
                if annual_avg is not None:
                    weighted_scores.append({
                        "score": annual_avg * Decimal(cs.coefficient),
                        "coef": cs.coefficient,
                        "fail": annual_avg < Decimal(10),
                    })
                else:
                    weighted_scores.append(None)

            total_coef = sum(
                cs.coefficient for i, cs in enumerate(class_subjects)
                if weighted_scores[i] is not None
            )
            total_score = sum(
                (ws["score"] for ws in weighted_scores if ws is not None), Decimal(0)
            )
            average = (
                (total_score / Decimal(total_coef)).quantize(Decimal("0.01"))
                if total_coef > 0 else Decimal(0)
            )

            has_marks = total_coef > 0
            if not has_marks:
                # Skip students with no marks entirely.
                continue
            rows.append({
                "student": student,
                "weighted_scores": weighted_scores,
                "total_coef": total_coef,
                "total_score": total_score.quantize(Decimal("0.01")),
                "average": average,
                "has_marks": True,
                "remark": _annual_remark(average, promotion_mark, dismissal_mark),
            })

        # Sort and rank (nominal)
        sorted_rows = sorted(
            rows,
            key=lambda r: r["average"] if r["average"] is not None else Decimal(0),
            reverse=True,
        )
        rank_map = {}
        current_rank = 1
        for i, r in enumerate(sorted_rows):
            if i > 0 and r["average"] < sorted_rows[i - 1]["average"]:
                current_rank = i + 1
            rank_map[r["student"].pk] = _ordinal(current_rank)
        for r in rows:
            r["rank"] = rank_map.get(r["student"].pk, "")

        num_sat = len(rows)
        num_passed = len([r for r in rows if r["average"] >= Decimal(10)])
        class_avg = (
            (sum(r["average"] for r in rows) / Decimal(len(rows)))
            .quantize(Decimal("0.01"))
            if rows else Decimal(0)
        )
        success_rate = (
            (Decimal(num_passed) / Decimal(num_sat) * Decimal(100)).quantize(Decimal("0.1"))
            if num_sat > 0 else Decimal(0)
        )

        class_master = ""
        class_master_signature = ""
        cm = TeacherAssignment.objects.filter(
            school_class=self.school_class, is_class_master=True, is_active=True,
        ).select_related("teacher").first()
        if cm:
            class_master = f"{cm.teacher.first_name} {cm.teacher.last_name}"
            class_master_signature = cm.teacher.signature.url if cm.teacher.signature else ""

        return {
            "school": self.school,
            "school_class": self.school_class,
            "terms": terms,
            "class_subjects": class_subjects,
            "rows": rows,
            "enrolment_m": len([s for s in students if s.sex == "M"]),
            "enrolment_f": len([s for s in students if s.sex == "F"]),
            "enrolment_total": len(students),
            "num_sat": num_sat,
            "num_passed": num_passed,
            "class_average": class_avg,
            "success_rate": success_rate,
            "class_master": class_master,
            "class_master_signature": class_master_signature,
            "is_annual": True,
        }

    def filename(self) -> str:
        return f"mark_sheet_annual_{self.school_class.code}_{self.year_start}_{self.year_end}.pdf"
