import base64
import hashlib
import hmac
import json
from datetime import date

from django.conf import settings
from django.db import models


class License(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("expired", "Expired"),
        ("revoked", "Revoked"),
    ]

    product_key = models.CharField(max_length=255, unique=True)
    school = models.ForeignKey(
        "core.School",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="licenses",
    )
    school_name = models.CharField(max_length=255)
    max_students = models.PositiveIntegerField(default=500)
    max_devices = models.PositiveSmallIntegerField(default=3)
    issued_date = models.DateField(auto_now_add=True)
    expires_at = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
    activated_at = models.DateTimeField(null=True, blank=True)
    machine_id = models.CharField(max_length=128, blank=True)
    activation_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "License"
        verbose_name_plural = "Licenses"

    def __str__(self) -> str:
        return f"{self.school_name} ({self.get_status_display()})"

    @property
    def is_valid(self) -> bool:
        return self.status == "active" and self.expires_at >= date.today()

    @property
    def days_remaining(self) -> int:
        return (self.expires_at - date.today()).days

    @classmethod
    def generate_product_key(
        cls,
        school_name: str,
        max_students: int,
        max_devices: int,
        expires: date,
        secret_key: str | None = None,
    ) -> str:
        """Build a signed ``OC-<signature>-<payload>`` product key (HMAC-SHA256)."""
        secret = secret_key or settings.LICENSE_SECRET_KEY
        payload = {
            "school": school_name,
            "max_students": max_students,
            "max_devices": max_devices,
            "expires": expires.isoformat(),
        }
        payload_bytes = json.dumps(payload, sort_keys=True).encode()
        signature = hmac.new(
            secret.encode(),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()[:16]
        raw = base64.urlsafe_b64encode(payload_bytes).decode().rstrip("=")
        return f"OC-{signature}-{raw}"

    @classmethod
    def verify_product_key(cls, product_key: str, secret_key: str) -> dict | None:
        """Return the decoded payload when the key's HMAC signature is valid."""
        parts = product_key.split("-", 2)
        if len(parts) != 3 or parts[0] != "OC":
            return None
        signature, raw = parts[1], parts[2]
        padding = 4 - len(raw) % 4
        try:
            payload = json.loads(base64.urlsafe_b64decode(raw + "=" * padding))
        except (TypeError, ValueError):
            return None
        expected = hmac.new(
            secret_key.encode(),
            json.dumps(payload, sort_keys=True).encode(),
            hashlib.sha256,
        ).hexdigest()[:16]
        if not hmac.compare_digest(signature, expected):
            return None
        return payload

    def validate_key(self, secret_key: str) -> bool:
        """Validate the HMAC signature embedded in the product key."""
        return self.verify_product_key(self.product_key, secret_key) is not None

    @classmethod
    def get_active(cls):
        """Return the active, non-expired license, or None."""
        return (
            cls.objects.filter(status="active", expires_at__gte=date.today())
            .order_by("-expires_at")
            .first()
        )

    @classmethod
    def get_active_for_school(cls, school):
        """Return the active, non-expired license for a given school, or None."""
        if not school:
            return None
        return (
            cls.objects.filter(
                school=school, status="active", expires_at__gte=date.today()
            )
            .order_by("-expires_at")
            .first()
        )
