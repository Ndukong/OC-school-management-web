import base64
import hashlib
import hmac
import json
from datetime import date, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Generate a product key for a school"

    def add_arguments(self, parser):
        parser.add_argument("school_name", type=str)
        parser.add_argument("--max-students", type=int, default=500)
        parser.add_argument("--max-devices", type=int, default=3)
        parser.add_argument("--days", type=int, default=365)

    def handle(self, *args, **options):
        payload = {
            "school": options["school_name"],
            "max_students": options["max_students"],
            "max_devices": options["max_devices"],
            "expires": str(date.today() + timedelta(days=options["days"])),
        }
        payload_bytes = json.dumps(payload, sort_keys=True).encode()
        signature = hmac.new(
            settings.LICENSE_SECRET_KEY.encode(),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()[:16]

        key_raw = base64.urlsafe_b64encode(payload_bytes).decode().rstrip("=")
        product_key = f"OC-{signature}-{key_raw}"

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Product Key:  {product_key}"))
        self.stdout.write(f"School:       {options['school_name']}")
        self.stdout.write(f"Max Students: {options['max_students']}")
        self.stdout.write(f"Max Devices:  {options['max_devices']}")
        self.stdout.write(f"Expires:      {payload['expires']}")
        self.stdout.write("")
