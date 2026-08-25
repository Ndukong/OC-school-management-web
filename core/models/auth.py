from django.contrib.auth.models import User
from django.db import models

from .school import School, SchoolClass, Subject


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ("superuser", "Superuser"),
        ("admin", "Administrator"),
        ("bursar", "Bursar"),
        ("class_master", "Class Master"),
        ("teacher", "Teacher"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    school = models.ForeignKey(
        School,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_profiles",
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="teacher")
    phone = models.CharField(max_length=50, blank=True)
    teacher = models.OneToOneField(
        "Teacher",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_profile",
        help_text="Link to Teacher record (for teachers and class masters)",
    )

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self) -> str:
        return f"{self.user.username} ({self.get_role_display()})"

    @property
    def assigned_classes(self):
        """Classes this user can access based on their teacher assignments."""
        if self.teacher:
            return SchoolClass.objects.filter(
                teacher_assignments__teacher=self.teacher,
                teacher_assignments__is_active=True,
            ).distinct()
        return SchoolClass.objects.none()

    @property
    def assigned_subjects(self):
        """Subjects this user can access based on their teacher assignments."""
        if self.teacher:
            return Subject.objects.filter(
                teacher_assignments__teacher=self.teacher,
                teacher_assignments__is_active=True,
            ).distinct()
        return Subject.objects.none()
