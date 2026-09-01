"""One-shot demo seeding for a fresh deployment (e.g. Railway).

    python manage.py seed_demo_school [--force] [--school-name ...] [--password ...]

Creates the demo school + an active license, then chains:
    seed_demo_forms -> import_xlsx_defaults -> seed_demo_students_marks

Self-guarding: if ANY school already exists the command exits without
touching anything, so it is safe to keep in the release pipeline. Real
deployments (a real school already configured) are never affected.
"""

import json

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from core.models import License, School

DEMO_SCHOOL_NAME = "Hope Bilingual College"
DEMO_MATRICULE = "HBC-001"
DEMO_LICENSE_DAYS = 365
DEMO_LICENSE_MAX_STUDENTS = 1000


class Command(BaseCommand):
    help = "Seed the full demo school (structure, staff, students, marks) once."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Run even when schools already exist (targets the first school).",
        )
        parser.add_argument(
            "--school-name",
            type=str,
            default=DEMO_SCHOOL_NAME,
            help=f"Name for the created demo school (default {DEMO_SCHOOL_NAME!r}).",
        )
        parser.add_argument(
            "--password",
            type=str,
            default="demo1234",
            help="Password for demo staff logins (default demo1234).",
        )

    def handle(self, *args, **options):
        school = School.objects.first()
        if school is not None and not options["force"]:
            self.stdout.write(
                self.style.WARNING(
                    f"School(s) already exist ({school.name_en}) — skipping demo "
                    "seeding. Run with --force to seed a separate demo school."
                )
            )
            return

        if school is None or options["force"]:
            matricule = DEMO_MATRICULE
            suffix = 1
            while School.objects.filter(matricule=matricule).exists():
                suffix += 1
                matricule = f"{DEMO_MATRICULE}-{suffix}"
            school = School.objects.create(
                name_en=options["school_name"],
                matricule=matricule,
                region_en="North West",
                division_en="Mezam",
            )
            self.stdout.write(
                self.style.SUCCESS(f"Created school: {school.name_en} ({matricule})")
            )

        if License.objects.filter(school=school).exists():
            self.stdout.write("License: already present, keeping it.")
        else:
            from datetime import date, timedelta

            License.objects.create(
                product_key=f"OC-demo-{school.matricule}",
                school=school,
                school_name=school.name_en,
                max_students=DEMO_LICENSE_MAX_STUDENTS,
                expires_at=date.today() + timedelta(days=DEMO_LICENSE_DAYS),
                status="active",
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"License: active for {DEMO_LICENSE_DAYS} days "
                    f"({DEMO_LICENSE_MAX_STUDENTS} student slots)."
                )
            )

        self.stdout.write("Seeding classes, subjects, teachers and students...")
        call_command(
            "seed_demo_forms",
            school=str(school.pk),
            password=options["password"],
        )

        self.stdout.write("Importing government subjects and competencies...")
        call_command("import_xlsx_defaults", school=str(school.pk), auto=True)

        self.stdout.write("Generating demo marks and computing results...")
        call_command("seed_demo_students_marks")

        self.stdout.write(
            self.style.SUCCESS(
                "Demo school ready. Staff logins use the password set via "
                "--password (default demo1234); usernames are logged above."
            )
        )
