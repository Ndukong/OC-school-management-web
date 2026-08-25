from decimal import Decimal

from core.models import (
    AcademicTerm,
    SchoolClass,
    Student,
    TermResult,
)
from core.utils.reports import BaseReport


class ResultsSummary(BaseReport):
    template_name = "reports/results_summary.html"
    css_files = ["reports/css/report.css"]

    def __init__(self, school_class: SchoolClass, term: AcademicTerm, school):
        self.school_class = school_class
        self.term = term
        self.school = school

    def get_context_data(self) -> dict:
        results = list(
            TermResult.objects.filter(
                student__enrollments__school_class=self.school_class,
                academic_term=self.term,
            ).select_related("student").distinct()
        )

        # Only count students with an average (enrolled and sat)
        enrolled = Student.objects.filter(
            enrollments__school_class=self.school_class,
            enrollments__academic_term=self.term,
        )
        total_m = enrolled.filter(sex="M").count()
        total_f = enrolled.filter(sex="F").count()
        total = total_m + total_f

        sat_results = [r for r in results if r.average and r.average > 0]
        num_sat = len(sat_results)
        sat_m = len([r for r in sat_results if r.student.sex == "M"])
        sat_f = num_sat - sat_m
        num_passed = len([r for r in sat_results if r.average >= Decimal(10)])
        passed_m = len([r for r in sat_results if r.average >= Decimal(10) and r.student.sex == "M"])
        passed_f = num_passed - passed_m
        class_avg = (
            (sum(r.average for r in sat_results) / Decimal(num_sat)).quantize(Decimal("0.01"))
            if num_sat > 0 else Decimal(0)
        )
        success_rate = (
            (Decimal(num_passed) / Decimal(num_sat) * Decimal(100)).quantize(Decimal("0.1"))
            if num_sat > 0 else Decimal(0)
        )

        # Sort by average descending for ranking
        sorted_results = sorted(sat_results, key=lambda r: r.average, reverse=True)
        top3 = [(i + 1, r.student, r.average) for i, r in enumerate(sorted_results[:3])]
        # Last 3 in order: last, second last, third last (with their real ranks)
        n = len(sorted_results)
        bottom3 = (
            [(n - i, sorted_results[n - 1 - i].student, sorted_results[n - 1 - i].average) for i in range(3)]
            if n >= 3 else []
        )

        return {
            "school": self.school,
            "school_class": self.school_class,
            "term": self.term,
            "enrolment_m": total_m,
            "enrolment_f": total_f,
            "enrolment_total": total,
            "num_sat": num_sat,
            "sat_m": sat_m,
            "sat_f": sat_f,
            "num_passed": num_passed,
            "passed_m": passed_m,
            "passed_f": passed_f,
            "success_rate": success_rate,
            "class_average": class_avg,
            "top3": top3,
            "bottom3": bottom3,
            "is_annual": False,
        }

    def filename(self) -> str:
        return f"results_summary_{self.school_class.code}_T{self.term.term_number}_{self.term.year_start}_{self.term.year_end}.pdf"


class AnnualResultsSummary(BaseReport):
    template_name = "reports/results_summary.html"
    css_files = ["reports/css/report.css"]

    def __init__(
        self, school_class: SchoolClass, year_start: int, year_end: int, school
    ):
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

        term_results = list(
            TermResult.objects.filter(
                student__enrollments__school_class=self.school_class,
                academic_term__in=terms,
            ).select_related("student").distinct()
        )

        # Enrolled in the class during the year
        enrolled = Student.objects.filter(
            enrollments__school_class=self.school_class,
            enrollments__academic_term__in=terms,
        ).distinct()
        total_m = enrolled.filter(sex="M").count()
        total_f = enrolled.filter(sex="F").count()
        total = total_m + total_f

        # Group term results by student to compute the annual average
        by_student: dict[int, list[Decimal]] = {}
        for r in term_results:
            by_student.setdefault(r.student_id, []).append(r.average)

        sat_rows = []
        for student in enrolled:
            avgs = by_student.get(student.pk, [])
            present = [a for a in avgs if a is not None and a > 0]
            if not present:
                continue
            annual_avg = (sum(present) / Decimal(len(present))).quantize(Decimal("0.01"))
            sat_rows.append((student, annual_avg))

        num_sat = len(sat_rows)
        sat_m = len([s for s, _ in sat_rows if s.sex == "M"])
        sat_f = num_sat - sat_m
        num_passed = len([avg for _, avg in sat_rows if avg >= Decimal(10)])
        passed_m = len([s for s, avg in sat_rows if avg >= Decimal(10) and s.sex == "M"])
        passed_f = num_passed - passed_m
        class_avg = (
            (sum(avg for _, avg in sat_rows) / Decimal(num_sat)).quantize(Decimal("0.01"))
            if num_sat > 0 else Decimal(0)
        )
        success_rate = (
            (Decimal(num_passed) / Decimal(num_sat) * Decimal(100)).quantize(Decimal("0.1"))
            if num_sat > 0 else Decimal(0)
        )

        sat_rows.sort(key=lambda row: row[1], reverse=True)
        top3 = [(i + 1, s, avg) for i, (s, avg) in enumerate(sat_rows[:3])]
        bottom3 = (
            [(len(sat_rows) - i, s, avg) for i, (s, avg) in enumerate(reversed(sat_rows[-3:]))]
            if len(sat_rows) >= 3 else []
        )

        return {
            "school": self.school,
            "school_class": self.school_class,
            "terms": terms,
            "term": terms[0] if terms else None,
            "enrolment_m": total_m,
            "enrolment_f": total_f,
            "enrolment_total": total,
            "num_sat": num_sat,
            "sat_m": sat_m,
            "sat_f": sat_f,
            "num_passed": num_passed,
            "passed_m": passed_m,
            "passed_f": passed_f,
            "success_rate": success_rate,
            "class_average": class_avg,
            "top3": top3,
            "bottom3": bottom3,
            "is_annual": True,
        }

    def filename(self) -> str:
        return f"results_summary_annual_{self.school_class.code}_{self.year_start}_{self.year_end}.pdf"
