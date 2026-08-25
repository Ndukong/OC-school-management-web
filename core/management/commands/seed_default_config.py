from django.core.management.base import BaseCommand

from core.models import AcademicTerm, School, SchoolClass, Subject

CAMEROON_SUBJECTS = [
    ("English Language", "ENL", 1),
    ("French Language", "FRE", 2),
    ("Mathematics", "MAT", 3),
    ("Physics", "PHY", 4),
    ("Chemistry", "CHM", 5),
    ("Biology", "BIO", 6),
    ("History", "HIS", 7),
    ("Geography", "GEO", 8),
    ("Civic Education", "CVE", 9),
    ("Computer Science", "CMP", 10),
    ("Economics", "ECN", 11),
    ("Food & Nutrition", "FND", 12),
    ("Art & Design", "ATD", 13),
    ("Music", "MUS", 14),
    ("Physical Education", "PED", 15),
    ("Entrepreneurship", "ENT", 16),
    ("Philosophy", "PHI", 17),
    ("Logic", "LOG", 18),
    ("Ethics", "ETH", 19),
    ("German", "GER", 20),
    ("Arabic", "ARB", 21),
    ("Chinese", "CHN", 22),
    ("Religious Studies", "RST", 23),
    ("Literature in English", "LIE", 24),
    ("Literature in French", "LIF", 25),
    ("Further Mathematics", "FMT", 26),
    ("Technical Drawing", "TDG", 27),
    ("Food Science", "FDS", 28),
    ("Clothing & Textile", "CLT", 29),
    ("Home Economics", "HEC", 30),
]

CAMEROON_CLASSES = [
    ("Form 1", "F1", 1, "first", "General"),
    ("Form 2", "F2", 2, "first", "General"),
    ("Form 3", "F3", 3, "first", "General"),
    ("Form 4", "F4", 4, "first", "General"),
    ("Form 5", "F5", 5, "first", "General"),
    ("Lower Sixth", "LS", 6, "second", "Arts"),
    ("Upper Sixth", "US", 7, "second", "Arts"),
]


class Command(BaseCommand):
    help = (
        "Seed default Cameroon subjects and class configuration. "
        "Run after first-time setup or when configuring a new school."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--auto",
            action="store_true",
            help="Skip confirmation prompt",
        )
        parser.add_argument(
            "--school",
            type=str,
            default=None,
            help="Seed defaults for the school with this pk (multi-tenant).",
        )

    def handle(self, *args, **options):
        if options["school"]:
            school = School.objects.filter(pk=options["school"]).first()
        else:
            school = School.objects.filter(is_active=True).first()
            if not school:
                school = School.objects.first()
        if not school:
            self.stderr.write(
                self.style.ERROR(
                    "No school found. Run the activation wizard first "
                    "(open http://127.0.0.1:8000 in your browser)."
                )
            )
            return

        self.stdout.write(f"Configuring defaults for: {school.name_en}")

        if not options["auto"]:
            confirm = input("Proceed? [y/N]: ").strip().lower()
            if confirm != "y":
                self.stdout.write("Cancelled.")
                return

        subj_count = 0
        for name, code, sort_order in CAMEROON_SUBJECTS:
            _, created = Subject.objects.get_or_create(
                school=school,
                code=code,
                defaults={"name": name, "sort_order": sort_order},
            )
            if created:
                subj_count += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"  Subjects: {subj_count} new ({len(CAMEROON_SUBJECTS)} total)"
            )
        )

        class_count = 0
        for name, code, form_level, cycle, stream in CAMEROON_CLASSES:
            _, created = SchoolClass.objects.get_or_create(
                school=school,
                code=code,
                defaults={
                    "name": name,
                    "form_level": form_level,
                    "cycle": cycle,
                    "stream": stream,
                    "sort_order": form_level,
                    "promotion_mark": 10.0,
                    "dismissal_mark": 6.0,
                },
            )
            if created:
                class_count += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"  Classes: {class_count} new ({len(CAMEROON_CLASSES)} total)"
            )
        )

        current_year = 2025
        term_count = 0
        for term_num in range(1, 4):
            _, created = AcademicTerm.objects.get_or_create(
                school=school,
                term_number=term_num,
                year_start=current_year,
                year_end=current_year + 1,
                defaults={"is_current": term_num == 1},
            )
            if created:
                term_count += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"  Terms: {term_count} new for {current_year}/{current_year + 1}"
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone! School '{school.name_en}' is ready.\n"
                f"  Go to Settings > School Profile to update your details,\n"
                f"  then Settings > Subjects to review the subject list."
            )
        )
