from django.db import models

from .school import School, SchoolClass, Subject


class Teacher(models.Model):
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="teachers"
    )
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    teacher_code = models.CharField(
        max_length=30, blank=True,
        help_text="Short code used for login (e.g., T001). Leave blank to match by email or name."
    )
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    signature = models.ImageField(
        upload_to="teachers/signatures/", blank=True
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Teacher"
        verbose_name_plural = "Teachers"
        ordering = ["first_name", "last_name"]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name}"


class TeacherAssignment(models.Model):
    teacher = models.ForeignKey(
        Teacher, on_delete=models.CASCADE, related_name="assignments"
    )
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.CASCADE, related_name="teacher_assignments"
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="teacher_assignments"
    )
    is_class_master = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Teacher Assignment"
        verbose_name_plural = "Teacher Assignments"
        unique_together = [["teacher", "school_class", "subject"]]

    def __str__(self) -> str:
        return f"{self.teacher} - {self.subject.code} ({self.school_class})"
