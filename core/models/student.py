from django.core.validators import MinLengthValidator
from django.db import models

from .school import AcademicTerm, School, SchoolClass


class Student(models.Model):
    SEX_CHOICES = [("M", "Male"), ("F", "Female")]

    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="students"
    )
    first_name = models.CharField(max_length=150)
    other_names = models.CharField(max_length=255, blank=True)
    sex = models.CharField(max_length=1, choices=SEX_CHOICES)
    unique_id = models.CharField(
        max_length=9,
        validators=[MinLengthValidator(9)],
        unique=True,
        help_text="9-digit state ID",
    )
    repeater = models.BooleanField(default=False)
    date_of_birth = models.DateField()
    place_of_birth = models.CharField(max_length=255)
    guardian_name = models.CharField(max_length=255)
    guardian_contact = models.CharField(max_length=50, blank=True)
    guardian_address = models.TextField(blank=True)
    division_of_origin = models.CharField(max_length=255)
    sub_division_of_origin = models.CharField(max_length=255, blank=True, help_text="Sub-division/Arrondissement of origin")
    region_of_origin = models.CharField(max_length=255)
    father_name = models.CharField(max_length=255, blank=True)
    mother_name = models.CharField(max_length=255, blank=True)
    parent_contact = models.CharField(max_length=50, blank=True)
    photo = models.ImageField(upload_to="students/photos/", blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Student"
        verbose_name_plural = "Students"
        ordering = ["first_name", "other_names"]

    def __str__(self) -> str:
        return f"{self.first_name} {self.other_names}".strip() if self.other_names else self.first_name

    @property
    def full_name(self) -> str:
        parts = [self.first_name]
        if self.other_names:
            parts.append(self.other_names)
        return " ".join(parts)


class StudentEnrollment(models.Model):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="enrollments"
    )
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.CASCADE, related_name="enrollments"
    )
    academic_term = models.ForeignKey(
        AcademicTerm, on_delete=models.CASCADE, related_name="enrollments"
    )
    date_enrolled = models.DateField(auto_now_add=True)

    class Meta:
        verbose_name = "Student Enrollment"
        verbose_name_plural = "Student Enrollments"
        unique_together = [["student", "academic_term"]]

    def __str__(self) -> str:
        return f"{self.student} - {self.school_class} ({self.academic_term})"
