from django.core.management.base import BaseCommand, CommandError

from core.models import AcademicTerm, School, SchoolClass, Student
from core.utils.mark_sheet import AnnualMarkSheet, MarkSheet
from core.utils.report_card import AnnualReportCard, TermReportCard


class Command(BaseCommand):
    help = "Render a report card or mark sheet PDF"

    def add_arguments(self, parser):
        parser.add_argument("--report", type=str, default="report_card",
            choices=["report_card", "annual", "mark_sheet", "annual_mark_sheet"])
        parser.add_argument("--student", type=str, help="Student unique_id")
        parser.add_argument("--class", type=str, dest="class_code", help="Class code (e.g. F2)")
        parser.add_argument("--school", type=int, help="School ID")
        parser.add_argument("--term", type=int, help="Term number (1, 2, 3)")
        parser.add_argument("--year-start", type=int, help="Academic year start")
        parser.add_argument("--year-end", type=int, help="Academic year end")
        parser.add_argument("--output", type=str, default="", help="Output file path")

    def handle(self, *args, **options):
        report_type = options["report"]
        student_id = options.get("student")
        school_id = options.get("school") or 1
        term_num = options.get("term") or 1
        year_start = options.get("year_start") or 2025
        year_end = options.get("year_end") or 2026

        try:
            school = School.objects.get(pk=school_id)
        except School.DoesNotExist:
            raise CommandError(f"School with ID {school_id} not found")

        if student_id:
            try:
                student = Student.objects.get(unique_id=student_id, school=school)
            except Student.DoesNotExist:
                raise CommandError(f"Student with ID {student_id} not found in school {school_id}")
        else:
            student = Student.objects.filter(school=school).first()
            if not student:
                raise CommandError("No students found. Create a student first.")
            self.stdout.write(f"Using first student: {student}")

        if report_type == "mark_sheet":
            class_code = options.get("class_code")
            if not class_code:
                raise CommandError("--class is required for mark_sheet reports")
            school_class = SchoolClass.objects.filter(school=school, code=class_code).first()
            if not school_class:
                raise CommandError(f"Class with code '{class_code}' not found")
            try:
                term = AcademicTerm.objects.get(
                    school=school, term_number=term_num,
                    year_start=year_start, year_end=year_end,
                )
            except AcademicTerm.DoesNotExist:
                raise CommandError(f"Term {term_num} {year_start}/{year_end} not found")
            report = MarkSheet(school_class, term, school)
        elif report_type == "annual_mark_sheet":
            class_code = options.get("class_code")
            if not class_code:
                raise CommandError("--class is required for annual_mark_sheet reports")
            school_class = SchoolClass.objects.filter(school=school, code=class_code).first()
            if not school_class:
                raise CommandError(f"Class with code '{class_code}' not found")
            report = AnnualMarkSheet(school_class, year_start, year_end, school)
        elif report_type == "report_card":
            try:
                term = AcademicTerm.objects.get(
                    school=school, term_number=term_num,
                    year_start=year_start, year_end=year_end,
                )
            except AcademicTerm.DoesNotExist:
                raise CommandError(f"Term {term_num} {year_start}/{year_end} not found")
            report = TermReportCard(student, term, school)
        else:
            report = AnnualReportCard(student, year_start, year_end, school)

        output = options.get("output") or report.filename()
        pdf_bytes = report.render_pdf()
        with open(output, "wb") as f:
            f.write(pdf_bytes)
        self.stdout.write(self.style.SUCCESS(f"Report saved to {output}"))
