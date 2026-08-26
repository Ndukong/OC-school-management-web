import hashlib
import hmac
import json
from datetime import date

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

    def validate_key(self, secret_key: str) -> bool:
        """Validate the HMAC signature embedded in the product key."""
        parts = self.product_key.split("-", 2)
        if len(parts) != 3 or parts[0] != "OC":
            return False
        signature = parts[1]
        raw = parts[2]
        padding = 4 - len(raw) % 4
        raw_padded = raw + "=" * padding
        import base64

        try:
            payload_bytes = base64.urlsafe_b64decode(raw_padded)
        except (ValueError, TypeError):
            return False
        payload = json.loads(payload_bytes)
        expected = hmac.new(
            secret_key.encode(),
            json.dumps(payload, sort_keys=True).encode(),
            hashlib.sha256,
        ).hexdigest()[:16]
        return hmac.compare_digest(signature, expected)

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
