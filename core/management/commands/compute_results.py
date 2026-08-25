from django.core.management.base import BaseCommand, CommandError

from core.models import AcademicTerm, School, SchoolClass
from core.utils.compute_results import compute_term_results


class Command(BaseCommand):
    help = "Compute subject averages and term results for a class and term"

    def add_arguments(self, parser):
        parser.add_argument(
            "--class", type=str, dest="class_code", help="Class code (e.g. F2)"
        )
        parser.add_argument("--class-id", type=int, help="Class ID")
        parser.add_argument("--school", type=int, default=1, help="School ID")
        parser.add_argument("--term", type=int, default=1, help="Term number (1, 2, 3)")
        parser.add_argument("--year-start", type=int, default=2025)
        parser.add_argument("--year-end", type=int, default=2026)

    def handle(self, *args, **options):
        try:
            school = School.objects.get(pk=options["school"])
        except School.DoesNotExist:
            raise CommandError(f"School with ID {options['school']} not found")

        if options["class_id"]:
            try:
                school_class = SchoolClass.objects.get(pk=options["class_id"])
            except SchoolClass.DoesNotExist:
                raise CommandError(f"Class with ID {options['class_id']} not found")
        else:
            class_code = options["class_code"]
            if not class_code:
                raise CommandError("--class (code) or --class-id is required")
            school_class = SchoolClass.objects.filter(
                school=school, code=class_code
            ).first()
            if not school_class:
                raise CommandError(f"Class with code '{class_code}' not found")

        try:
            term = AcademicTerm.objects.get(
                school=school,
                term_number=options["term"],
                year_start=options["year_start"],
                year_end=options["year_end"],
            )
        except AcademicTerm.DoesNotExist:
            raise CommandError(
                f"Term {options['term']} {options['year_start']}/{options['year_end']} not found"
            )

        stats = compute_term_results(school_class, term)
        self.stdout.write(f"{school_class} / {term}:")
        self.stdout.write(f"  Enrolled: {stats['enrolled']}")
        self.stdout.write(f"  Sat:      {stats['num_sat']}")
        self.stdout.write(f"  Passed:   {stats['num_passed']}")
        self.stdout.write(f"  Class avg: {stats['class_average']}")
        self.stdout.write(f"  Success:  {stats['success_rate']}%")
        self.stdout.write(self.style.SUCCESS("Done."))
