from django.core.management.base import BaseCommand

from core.utils.backup import create_backup_archive


class Command(BaseCommand):
    help = "Create a database backup"

    def add_arguments(self, parser):
        parser.add_argument(
            "--notes",
            type=str,
            default="",
            help="Notes for the backup",
        )
        parser.add_argument(
            "--type",
            type=str,
            default="full",
            choices=["full", "database"],
            help="Backup type: full (db+media) or database only",
        )

    def handle(self, *args, **options):
        notes = options["notes"]
        backup_type = options["type"]

        self.stdout.write(f"Creating {backup_type} backup...")
        history = create_backup_archive(notes=notes, backup_type=backup_type)
        self.stdout.write(
            self.style.SUCCESS(
                f"Backup created: {history.filename} ({history.size_display})"
            )
        )
