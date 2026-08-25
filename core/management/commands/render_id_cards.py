from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.models import School, Student


class Command(BaseCommand):
    help = "Generate test ID cards HTML for 4 students (view in browser, print to PDF)"

    def add_arguments(self, parser):
        parser.add_argument("--school", type=int, default=1, help="School ID")
        parser.add_argument("--output", type=str, default="test_id_cards.html")

    def handle(self, *args, **options):
        school_id = options["school"]
        output = options["output"]

        try:
            school = School.objects.get(pk=school_id)
        except School.DoesNotExist:
            raise CommandError(f"School {school_id} not found")

        students = list(Student.objects.filter(school=school, is_active=True)[:4])
        while len(students) < 4:
            i = len(students) + 1
            s = Student.objects.create(
                school=school,
                first_name=f"Student{i}",
                other_names=f"Test Other{i}",
                sex="M" if i % 2 else "F",
                unique_id=str(240000000 + i),
                date_of_birth=date(2010, i, 15),
                place_of_birth=f"Town{i}",
                guardian_name=f"Guardian{i}",
                guardian_contact=f"67{i}00000{i}",
                division_of_origin=f"Division{i}",
                sub_division_of_origin=f"SubDiv{i}",
                region_of_origin=f"Region{i}",
                father_name=f"Father{i}",
                mother_name=f"Mother{i}",
                parent_contact=f"69{i}00000{i}",
            )
            students.append(s)
            self.stdout.write(f"  Created fake student: {s.full_name}")

        self.stdout.write(f"Rendering ID cards for {len(students)} students...")

        from core.utils.student_id import render_full_set_html
        context = {"academic_year": "2025/2026", "today": date.today()}
        html = render_full_set_html(students, school, context)

        with open(output, "w", encoding="utf-8") as f:
            f.write(html)

        abs_path = Path(output).resolve()
        self.stdout.write(self.style.SUCCESS(f"ID cards HTML saved to {abs_path}"))
        self.stdout.write("To see images (logo, photo, seal), open this URL in your browser instead:")
        self.stdout.write("  http://127.0.0.1:8000/reports/id-cards/preview/")
        self.stdout.write("Then use Print > Save as PDF (A4 landscape, no margins, background graphics on).")
