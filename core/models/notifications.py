from django.db import models
from django.utils import timezone


class Notification(models.Model):
    TYPE_CHOICES = [
        ("report_ready", "Report Ready"),
        ("absence", "Absence Alert"),
        ("fee_reminder", "Fee Reminder"),
        ("system", "System"),
    ]
    PRIORITY_CHOICES = [
        ("low", "Low"),
        ("normal", "Normal"),
        ("high", "High"),
    ]

    recipient = models.ForeignKey(
        "auth.User", on_delete=models.CASCADE, related_name="notifications"
    )
    notification_type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default="normal")
    is_read = models.BooleanField(default=False)
    action_url = models.CharField(max_length=512, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"[{self.get_notification_type_display()}] {self.title}"

    def mark_read(self):
        self.is_read = True
        self.read_at = timezone.now()
        self.save(update_fields=["is_read", "read_at"])


class SMSConfig(models.Model):
    PROVIDER_CHOICES = [
        ("manual", "Manual / Bulk SMS"),
        ("twilio", "Twilio"),
        ("africastalking", "Africa's Talking"),
    ]

    school = models.OneToOneField(
        "School", on_delete=models.CASCADE, related_name="sms_config"
    )
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, default="manual")
    api_key = models.CharField(max_length=255, blank=True)
    api_secret = models.CharField(max_length=255, blank=True)
    sender_id = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=False)
    daily_limit = models.PositiveIntegerField(default=100, help_text="Max SMS per day")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "SMS Configuration"
        verbose_name_plural = "SMS Configurations"

    def __str__(self) -> str:
        return f"SMS Config ({self.get_provider_display()})"

    def messages_today(self):
        from django.utils import timezone as tz
        today = tz.localdate()
        return self.messages.filter(created_at__date=today).count()

    def can_send_today(self):
        return self.messages_today() < self.daily_limit


class SMSMessage(models.Model):
    STATUS_CHOICES = [
        ("queued", "Queued"),
        ("sending", "Sending"),
        ("sent", "Sent"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]

    config = models.ForeignKey(
        SMSConfig, on_delete=models.CASCADE, related_name="messages"
    )
    recipient_number = models.CharField(max_length=20)
    recipient_name = models.CharField(max_length=255, blank=True)
    message = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="queued")
    error_message = models.TextField(blank=True)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    retry_count = models.PositiveSmallIntegerField(default=0)
    max_retries = models.PositiveSmallIntegerField(default=3)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        verbose_name = "SMS Message"
        verbose_name_plural = "SMS Messages"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"SMS to {self.recipient_number} ({self.get_status_display()})"
