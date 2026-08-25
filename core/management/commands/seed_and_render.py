import random
from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.template.loader import render_to_string

from core.models import (
    AcademicTerm,
    School,
    SchoolClass,
    Student,
    StudentEnrollment,
    TermResult,
)

CLASSES_TO_SEED = ["F1", "F2", "F3", "F4", "F5"]


class Command(BaseCommand):
    help = "Seed sample term results and render a results summary report"

    def add_arguments(self, parser):
        parser.add_argument("--school", type=int, default=1)
        parser.add_argument("--term", type=int, default=1)
        parser.add_argument("--year-start", type=int, default=2025)
        parser.add_argument("--year-end", type=int, default=2026)
        parser.add_argument("--output", type=str, default="results_summary.html")

    def handle(self, *args, **options):
        school_id = options["school"]
        term_num = options["term"]
        year_start = options["year_start"]
        year_end = options["year_end"]
        output = options["output"]

        school = School.objects.get(pk=school_id)
        term = AcademicTerm.objects.get(
            school=school, term_number=term_num,
            year_start=year_start, year_end=year_end,
        )

        random.seed(42)
        TermResult.objects.filter(academic_term=term).delete()

        for code in CLASSES_TO_SEED:
            sc = SchoolClass.objects.filter(school=school, code=code).first()
            if not sc:
                continue

            students = list(Student.objects.filter(
                enrollments__school_class=sc,
                enrollments__academic_term=term,
            ))
            if not students:
                names_map = {
                    "F1": [("Nkengafac", "Wirba"), ("Efande", "Prisca"), ("Mbah", "Derick"), ("Ngo", "Sandrine"), ("Taku", "Arrey")],
                    "F3": [("Fonkem", "Nkwain"), ("Neba", "Clarisse"), ("Achiri", "Nformi"), ("Eyong", "Mireille"), ("Tabe", "Bate")],
                    "F4": [("Nfor", "Nkwenti"), ("Suh", "Ning"), ("Ngum", "Veronique"), ("Che", "Nji"), ("Kongnso", "Valery")],
                    "F5": [("Nkwain", "Fidelis"), ("Mforteh", "Shelly"), ("Nkwi", "Nchang"), ("Lum", "Neba"), ("Tanga", "Mbah")],
                }
                names = names_map.get(code, [(f"Sample{code}{i}", "Student") for i in range(1, 6)])
                for i, (first, last) in enumerate(names, start=1):
                    s = Student.objects.create(
                        school=school,
                        first_name=first,
                        other_names=last,
                        sex="M" if i % 2 else "F",
                        unique_id=f"99{code}{i:04d}",
                        date_of_birth=date(2008 + i, i, 15),
                        place_of_birth="Buea",
                        guardian_name=f"Mr. {last}",
                        guardian_contact=f"677{i}00000{i}",
                        division_of_origin="Fako",
                        sub_division_of_origin="Buea",
                        region_of_origin="South West",
                    )
                    StudentEnrollment.objects.create(student=s, school_class=sc, academic_term=term)
                    students.append(s)

            for s in students:
                avg = Decimal(str(round(random.uniform(4.0, 18.0), 2)))
                TermResult.objects.update_or_create(
                    student=s, academic_term=term,
                    defaults={
                        "total_score": avg * Decimal(8),
                        "total_coef": 8,
                        "average": avg,
                    },
                )

        # Render
        from core.utils.results_summary import ResultsSummary

        all_classes = SchoolClass.objects.filter(school=school, code__in=CLASSES_TO_SEED).order_by("sort_order")
        sections = []
        for sc in all_classes:
            report = ResultsSummary(sc, term, school)
            ctx = report.get_context_data()
            sections.append(render_to_string("reports/results_summary_section.html", ctx))

        full_html = render_to_string("reports/results_summary.html", {
            "school": school, "term": term, "sections": sections,
        })

        with open(output, "w", encoding="utf-8") as f:
            f.write(full_html)
        self.stdout.write(self.style.SUCCESS(f"Saved to {output}"))
