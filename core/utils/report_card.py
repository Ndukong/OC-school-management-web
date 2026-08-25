from decimal import Decimal

from django.db.models import Sum

from core.models import (
    AcademicTerm,
    Competency,
    CompetencyScore,
    DisciplineSummary,
    School,
    SchoolClass,
    Student,
    Subject,
    SubjectAverage,
    TeacherAssignment,
    TermResult,
)
from core.utils.grading import (
    compute_grade,
    compute_promotion_decision,
    compute_remark,
    compute_subject_average,
    compute_term_total,
)
from core.utils.reports import BaseReport


class TermReportCard(BaseReport):
    template_name = "reports/report_card.html"
    css_files = ["reports/css/report.css"]

    def __init__(self, student: Student, term: AcademicTerm, school: School):
        self.student = student
        self.term = term
        self.school = school

    def _get_enrollment(self) -> SchoolClass | None:
        enrollment = (
            self.student.enrollments.filter(academic_term=self.term)
            .select_related("school_class")
            .first()
        )
        return enrollment.school_class if enrollment else None

    def _get_class_subjects(self, school_class: SchoolClass) -> list:
        return list(
            school_class.subjects.select_related("subject").order_by("sort_order")
        )

    def _get_competencies(self, subject: Subject) -> list:
        competencies = list(
            subject.competencies.filter(term=self.term).order_by("sort_order")
        )
        if len(competencies) == 1:
            # Some subjects define a single competency for the term; the report
            # card must show at least two, so the competency is repeated.
            competencies.append(competencies[0])
        return competencies

    def _get_competency_scores(self, competencies: list) -> dict:
        scores = CompetencyScore.objects.filter(
            student=self.student,
            competency__in=competencies,
            academic_term=self.term,
        )
        score_map = {}
        for c in competencies:
            try:
                s = scores.get(competency=c)
                score_map[c.pk] = s.score
            except CompetencyScore.DoesNotExist:
                score_map[c.pk] = None
        return score_map

    def _get_teacher_for_subject(
        self, school_class: SchoolClass, subject: Subject
    ) -> tuple[str, str]:
        assignment = (
            TeacherAssignment.objects.filter(
                school_class=school_class, subject=subject, is_active=True
            )
            .select_related("teacher")
            .first()
        )
        if assignment:
            t = assignment.teacher
            name = t.first_name
            sig = t.signature.url if t.signature else ""
            return name, sig
        return "", ""

    def _get_class_master(self, school_class: SchoolClass) -> tuple[str, str]:
        assignment = (
            TeacherAssignment.objects.filter(
                school_class=school_class, is_class_master=True, is_active=True
            )
            .select_related("teacher")
            .first()
        )
        if assignment:
            t = assignment.teacher
            name = f"{t.first_name} {t.last_name}"
            sig = t.signature.url if t.signature else ""
            return name, sig
        return "", ""

    def _get_discipline(self) -> DisciplineSummary | None:
        try:
            return DisciplineSummary.objects.get(
                student=self.student, academic_term=self.term
            )
        except DisciplineSummary.DoesNotExist:
            return None

    def _get_enrolment_count(self, school_class: SchoolClass) -> dict:
        """Count only students who have an actual average for this term."""
        results = TermResult.objects.filter(
            student__enrollments__school_class=school_class,
            student__enrollments__academic_term=self.term,
            academic_term=self.term,
        )
        total = results.count()
        male = results.filter(student__sex="M").count()
        female = results.filter(student__sex="F").count()
        return {"total": total, "male": male, "female": female}

    def _get_class_profile(self, school_class: SchoolClass) -> dict:
        results = TermResult.objects.filter(
            student__enrollments__school_class=school_class,
            student__enrollments__academic_term=self.term,
            academic_term=self.term,
        )
        total = results.count()
        if total == 0:
            return {
                "class_average": Decimal(0),
                "number_passed": 0,
                "success_rate": Decimal(0),
            }
        passed = results.filter(average__gte=Decimal(10)).count()
        avg = (results.aggregate(avg=Sum("average"))["avg"] or Decimal(0)) / Decimal(
            total
        )
        return {
            "class_average": avg.quantize(Decimal("0.01")),
            "number_passed": passed,
            "success_rate": (
                Decimal(passed) / Decimal(total) * Decimal(100)
            ).quantize(Decimal("0.1")),
        }

    def get_context_data(self) -> dict:
        school_class = self._get_enrollment()
        subjects_data = []
        total_subjects = 0
        passed_subjects = 0
        weighted_scores = []
        class_master = ""
        enrolment = {"total": 0, "male": 0, "female": 0}
        class_profile = {
            "class_average": Decimal(0),
            "number_passed": 0,
            "success_rate": Decimal(0),
        }

        if school_class:
            class_master, class_master_sig = self._get_class_master(school_class)
            enrolment = self._get_enrolment_count(school_class)
            class_profile = self._get_class_profile(school_class)

            class_subjects = list(
                school_class.subjects.select_related("subject").order_by("sort_order")
            )
            subject_ids = [cs.subject_id for cs in class_subjects]

            # Fetch competencies, scores and teachers in bulk (avoids N+1).
            all_competencies = list(
                Competency.objects.filter(
                    subject_id__in=subject_ids, term=self.term
                ).order_by("subject_id", "sort_order")
            )
            comps_by_subject: dict[int, list] = {}
            for comp in all_competencies:
                comps_by_subject.setdefault(comp.subject_id, []).append(comp)

            all_scores = list(
                CompetencyScore.objects.filter(
                    student=self.student,
                    competency_id__in=[c.pk for c in all_competencies],
                    academic_term=self.term,
                ).values_list("competency_id", "score")
            )
            score_by_comp = {comp_id: score for comp_id, score in all_scores}

            assignments = list(
                TeacherAssignment.objects.filter(
                    school_class=school_class,
                    subject_id__in=subject_ids,
                    is_active=True,
                ).select_related("teacher")
            )
            teacher_by_subject = {a.subject_id: a for a in assignments}

            for cs in class_subjects:
                subject = cs.subject
                competencies = comps_by_subject.get(subject.pk, [])
                if len(competencies) == 1:
                    # Some subjects define a single competency for the term; the
                    # report card must show at least two, so it is repeated.
                    competencies = competencies + competencies

                comp_rows = []
                avg_scores = []
                has_score = False
                for comp in competencies:
                    sc = score_by_comp.get(comp.pk)
                    if sc is not None:
                        has_score = True
                        avg_scores.append(sc)
                        comp_rows.append({"description": comp.description, "score": sc})

                if not has_score:
                    continue

                subject_avg = compute_subject_average(avg_scores)
                assignment = teacher_by_subject.get(subject.pk)
                teacher_name = assignment.teacher.first_name if assignment else ""
                teacher_sig = (
                    assignment.teacher.signature.url
                    if assignment and assignment.teacher.signature
                    else ""
                )

                if subject_avg is not None:
                    total_subjects += 1
                    if subject_avg >= Decimal(10):
                        passed_subjects += 1
                    weighted_scores.append((subject_avg, cs.coefficient))

                subjects_data.append(
                    {
                        "subject": subject,
                        "coefficient": cs.coefficient,
                        "competencies": comp_rows,
                        "average": subject_avg,
                        "grade": (
                            compute_grade(subject_avg)
                            if subject_avg is not None
                            else ""
                        ),
                        "remark": (
                            compute_remark(subject_avg)
                            if subject_avg is not None
                            else ""
                        ),
                        "teacher_name": teacher_name,
                        "teacher_signature": teacher_sig,
                        "av_coef": (
                            subject_avg * cs.coefficient
                            if subject_avg is not None
                            else None
                        ),
                    }
                )

        total_weighted, total_coef, overall_avg = compute_term_total(weighted_scores)
        discipline = self._get_discipline()
        term_result = TermResult.objects.filter(
            student=self.student, academic_term=self.term
        ).first()

        return {
            "school": self.school,
            "student": self.student,
            "term": self.term,
            "school_class": school_class,
            "class_master": class_master,
            "class_master_signature": class_master_sig if school_class else "",
            "subjects_data": subjects_data,
            "total_subjects": total_subjects,
            "passed_subjects": passed_subjects,
            "total_score": total_weighted.quantize(Decimal("0.01")),
            "total_coef": total_coef,
            "average": overall_avg.quantize(Decimal("0.01")),
            "grade": compute_grade(overall_avg),
            "remark": compute_remark(overall_avg),
            "rank": term_result.rank if term_result else None,
            "remark_on_performance": (
                term_result.remark_on_performance if term_result else ""
            ),
            "discipline": discipline,
            "enrolment": enrolment,
            "class_profile": class_profile,
            "is_annual": False,
            "promotion_decision": None,
        }

    def filename(self) -> str:
        return f"report_card_{self.student.unique_id}_T{self.term.term_number}_{self.term.year_start}_{self.term.year_end}.pdf"


class AnnualReportCard(BaseReport):
    template_name = "reports/report_card.html"
    css_files = ["reports/css/report.css"]

    def __init__(
        self, student: Student, year_start: int, year_end: int, school: School
    ):
        self.student = student
        self.year_start = year_start
        self.year_end = year_end
        self.school = school

    def get_context_data(self) -> dict:
        terms = list(
            AcademicTerm.objects.filter(
                school=self.school, year_start=self.year_start, year_end=self.year_end
            ).order_by("term_number")
        )
        enrollment = (
            self.student.enrollments.filter(academic_term__in=terms)
            .select_related("school_class")
            .first()
        )
        school_class = enrollment.school_class if enrollment else None

        subjects_data = []
        total_subjects = 0
        passed_subjects = 0
        weighted = []
        class_master = ""
        class_master_sig = ""
        enrolment = {"total": 0, "male": 0, "female": 0}
        class_profile = {
            "class_average": Decimal(0),
            "number_passed": 0,
            "success_rate": Decimal(0),
        }

        if school_class:
            term_report = TermReportCard(self.student, terms[0], self.school) if terms else None
            if term_report:
                class_master, class_master_sig = term_report._get_class_master(school_class)

            annual_rows = []
            for student in Student.objects.filter(
                enrollments__school_class=school_class,
                enrollments__academic_term__in=terms,
                is_active=True,
            ).distinct():
                student_weighted = []
                for cs in school_class.subjects.select_related("subject").order_by("sort_order"):
                    term_avgs = list(
                        SubjectAverage.objects.filter(
                            student=student,
                            subject=cs.subject,
                            academic_term__in=terms,
                        ).values_list("average", flat=True)
                    )
                    subject_avg = compute_subject_average(term_avgs)
                    if subject_avg is not None:
                        student_weighted.append((subject_avg, cs.coefficient))
                if student_weighted:
                    _, _, student_avg = compute_term_total(student_weighted)
                    annual_rows.append((student, student_avg))

            annual_rows.sort(key=lambda row: row[1], reverse=True)
            enrolment = {
                "total": len(annual_rows),
                "male": sum(1 for student, _ in annual_rows if student.sex == "M"),
                "female": sum(1 for student, _ in annual_rows if student.sex == "F"),
            }
            if annual_rows:
                passed = sum(1 for _, avg in annual_rows if avg >= Decimal(10))
                class_average = (
                    sum((avg for _, avg in annual_rows), Decimal(0))
                    / Decimal(len(annual_rows))
                ).quantize(Decimal("0.01"))
                class_profile = {
                    "class_average": class_average,
                    "number_passed": passed,
                    "success_rate": (
                        Decimal(passed) / Decimal(len(annual_rows)) * Decimal(100)
                    ).quantize(Decimal("0.1")),
                }

            rank = None
            for index, (student, _) in enumerate(annual_rows, start=1):
                if student.pk == self.student.pk:
                    rank = index
                    break

            for cs in school_class.subjects.select_related("subject").order_by("sort_order"):
                subject = cs.subject
                per_term = {}
                for term_obj in terms:
                    try:
                        sa = SubjectAverage.objects.get(
                            student=self.student,
                            subject=subject,
                            academic_term=term_obj,
                        )
                        per_term[term_obj.term_number] = sa.average
                    except SubjectAverage.DoesNotExist:
                        per_term[term_obj.term_number] = None
                term_avgs = [per_term.get(t.term_number) for t in terms]
                present = [a for a in term_avgs if a is not None]
                subject_avg = compute_subject_average(present)
                if subject_avg is None:
                    continue

                teacher_name, teacher_sig = ("", "")
                if term_report:
                    teacher_name, teacher_sig = term_report._get_teacher_for_subject(
                        school_class, subject
                    )

                total_subjects += 1
                if subject_avg >= Decimal(10):
                    passed_subjects += 1
                weighted.append((subject_avg, cs.coefficient))
                subjects_data.append(
                    {
                        "subject": subject,
                        "coefficient": cs.coefficient,
                        "term_averages": term_avgs,
                        "average": subject_avg,
                        "grade": compute_grade(subject_avg),
                        "remark": compute_remark(subject_avg),
                        "teacher_name": teacher_name,
                        "teacher_signature": teacher_sig,
                        "av_coef": subject_avg * cs.coefficient,
                    }
                )

        total_weighted, total_coef, overall_avg = compute_term_total(weighted)
        promotion_mark = (
            Decimal(str(school_class.promotion_mark)) if school_class else Decimal(10)
        )
        dismissal_mark = (
            Decimal(str(school_class.dismissal_mark))
            if school_class and school_class.dismissal_mark
            else None
        )
        discipline_rows = DisciplineSummary.objects.filter(
            student=self.student, academic_term__in=terms
        )
        discipline = {
            "unjustified_abs_hours": sum(
                (row.unjustified_abs_hours for row in discipline_rows), Decimal(0)
            ),
            "justified_abs_hours": sum(
                (row.justified_abs_hours for row in discipline_rows), Decimal(0)
            ),
            "lateness_count": sum(row.lateness_count for row in discipline_rows),
            "punishment_hours": sum(
                (row.punishment_hours for row in discipline_rows), Decimal(0)
            ),
            "conduct_decision": "",
        }
        for decision in ["dismissal", "suspension", "reprimand", "warning"]:
            if discipline_rows.filter(conduct_decision=decision).exists():
                discipline["conduct_decision"] = decision
                break

        return {
            "school": self.school,
            "student": self.student,
            "terms": terms,
            "term": terms[0] if terms else None,
            "school_class": school_class,
            "class_master": class_master,
            "class_master_signature": class_master_sig,
            "subjects_data": subjects_data,
            "total_subjects": total_subjects,
            "passed_subjects": passed_subjects,
            "total_score": total_weighted.quantize(Decimal("0.01")),
            "total_coef": total_coef,
            "average": overall_avg.quantize(Decimal("0.01")),
            "grade": compute_grade(overall_avg),
            "remark": compute_remark(overall_avg),
            "rank": rank,
            "remark_on_performance": "",
            "discipline": discipline,
            "enrolment": enrolment,
            "class_profile": class_profile,
            "promotion_decision": compute_promotion_decision(
                overall_avg, promotion_mark, dismissal_mark=dismissal_mark
            ),
            "is_annual": True,
        }

    def filename(self) -> str:
        return f"annual_report_{self.student.unique_id}_{self.year_start}_{self.year_end}.pdf"
