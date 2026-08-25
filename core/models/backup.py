from django.db import models


class BackupHistory(models.Model):
    STATUS_CHOICES = [
        ("created", "Created"),
        ("restored", "Restored"),
        ("failed", "Failed"),
    ]
    TYPE_CHOICES = [
        ("full", "Full (DB + Media)"),
        ("database", "Database Only"),
    ]

    filename = models.CharField(max_length=255)
    filepath = models.CharField(max_length=512)
    file_size = models.PositiveBigIntegerField(default=0)
    backup_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default="full")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="created")
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        "auth.User", on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    restored_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Backup History"
        verbose_name_plural = "Backup Histories"
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.filename} ({self.get_status_display()})"

    @property
    def size_display(self) -> str:
        size = self.file_size
        if size < 1024:
            return f"{size} B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.1f} MB"
