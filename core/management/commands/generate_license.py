from datetime import date, timedelta

from django.core.management.base import BaseCommand

from core.models import License


class Command(BaseCommand):
    help = "Generate a product key for a school"

    def add_arguments(self, parser):
        parser.add_argument("school_name", type=str)
        parser.add_argument("--max-students", type=int, default=500)
        parser.add_argument("--max-devices", type=int, default=3)
        parser.add_argument("--days", type=int, default=365)

    def handle(self, *args, **options):
        product_key = License.generate_product_key(
            school_name=options["school_name"],
            max_students=options["max_students"],
            max_devices=options["max_devices"],
            expires=date.today() + timedelta(days=options["days"]),
        )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Product Key:  {product_key}"))
        self.stdout.write(f"School:       {options['school_name']}")
        self.stdout.write(f"Max Students: {options['max_students']}")
        self.stdout.write(f"Max Devices:  {options['max_devices']}")
        self.stdout.write(
            f"Expires:      {date.today() + timedelta(days=options['days'])}"
        )
        self.stdout.write("")
