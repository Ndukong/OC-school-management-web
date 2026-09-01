from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class School(models.Model):
    name_en = models.CharField(max_length=255)
    name_fr = models.CharField(max_length=255, blank=True)
    logo = models.ImageField(upload_to="schools/logos/", blank=True)
    seal = models.ImageField(upload_to="schools/seals/", blank=True)
    matricule = models.CharField(max_length=50, unique=True)
    phone = models.CharField(max_length=30, blank=True)
    region_en = models.CharField(max_length=255)
    region_fr = models.CharField(max_length=255, blank=True)
    division_en = models.CharField(max_length=255)
    division_fr = models.CharField(max_length=255, blank=True)
    motto_en = models.CharField(
        max_length=255, default="Peace - Work - Fatherland", blank=True
    )
    motto_fr = models.CharField(
        max_length=255, default="Paix - Travail - Patrie", blank=True
    )
    letterhead_line1_en = models.CharField(
        max_length=255, default="REPUBLIC OF CAMEROON", blank=True
    )
    letterhead_line1_fr = models.CharField(
        max_length=255, default="REPUBLIQUE DU CAMEROUN", blank=True
    )
    letterhead_line2_en = models.CharField(
        max_length=255, default="PEACE - WORK - FATHERLAND", blank=True
    )
    letterhead_line2_fr = models.CharField(
        max_length=255, default="PAIX - TRAVAIL - PATRIE", blank=True
    )
    letterhead_line3_en = models.CharField(max_length=255, blank=True)
    letterhead_line3_fr = models.CharField(max_length=255, blank=True)
    periods_per_day = models.PositiveSmallIntegerField(
        default=8,
        validators=[MinValueValidator(6), MaxValueValidator(10)],
        help_text="Number of teaching periods per day (6–10).",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "School"
        verbose_name_plural = "Schools"

    def __str__(self) -> str:
        return self.name_en


class SchoolClass(models.Model):
    CYCLE_CHOICES = [("first", "First Cycle"), ("second", "Second Cycle")]

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="classes")
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, help_text="e.g., F1, F2, LS, US")
    stream = models.CharField(
        max_length=50, blank=True, help_text="e.g., A, B, Industrial, Commercial"
    )
    cycle = models.CharField(max_length=10, choices=CYCLE_CHOICES, default="first")
    form_level = models.PositiveSmallIntegerField(
        default=1,
        help_text="Numeric form level (1=Form 1, 5=Form 5, 6=Lower Sixth, 7=Upper Sixth)",
    )
    promotion_mark = models.FloatField(default=10.0)
    dismissal_mark = models.FloatField(
        default=6.0,
        help_text="Annual average below which a student is dismissed at year end.",
    )
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Class"
        verbose_name_plural = "Classes"
        ordering = ["sort_order"]
        unique_together = [["school", "code", "stream"]]

    def __str__(self) -> str:
        return f"{self.name} {self.stream}".strip() if self.stream else self.name


class AcademicTerm(models.Model):
    TERM_CHOICES = [
        (1, "First Term"),
        (2, "Second Term"),
        (3, "Third Term"),
    ]

    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="terms")
    term_number = models.PositiveSmallIntegerField(choices=TERM_CHOICES)
    year_start = models.PositiveIntegerField()
    year_end = models.PositiveIntegerField()
    is_current = models.BooleanField(default=False)

    class Meta:
        verbose_name = "Academic Term"
        verbose_name_plural = "Academic Terms"
        unique_together = [["school", "term_number", "year_start", "year_end"]]
        constraints = [
            models.UniqueConstraint(
                fields=["school"],
                condition=models.Q(is_current=True),
                name="unique_current_term_per_school",
            )
        ]

    def save(self, *args, **kwargs):
        if self.is_current:
            AcademicTerm.objects.filter(school=self.school, is_current=True).exclude(
                pk=self.pk
            ).update(is_current=False)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.get_term_number_display()} - {self.year_start}/{self.year_end}"

    @property
    def label(self) -> str:
        return self.get_term_number_display()


class Subject(models.Model):
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="subjects"
    )
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=10, help_text="e.g., ENL, FRE, MAT")
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Subject"
        verbose_name_plural = "Subjects"
        ordering = ["sort_order"]
        unique_together = [["school", "code"]]

    def __str__(self) -> str:
        return f"{self.name} ({self.code})"


class Competency(models.Model):
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="competencies"
    )
    term = models.ForeignKey(
        AcademicTerm, on_delete=models.CASCADE, related_name="competencies"
    )
    form_level = models.PositiveSmallIntegerField(
        default=1, help_text="Form level (1-5) this competency applies to"
    )
    description = models.TextField()
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Competency"
        verbose_name_plural = "Competencies"
        ordering = ["subject", "form_level", "sort_order"]
        unique_together = [["subject", "term", "form_level", "sort_order"]]

    def __str__(self) -> str:
        return f"{self.subject.code} F{self.form_level} T{self.term.term_number}: {self.description[:60]}"


class ClassSubject(models.Model):
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.CASCADE, related_name="subjects"
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="class_subjects"
    )
    coefficient = models.PositiveSmallIntegerField(default=1)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Class Subject"
        verbose_name_plural = "Class Subjects"
        ordering = ["sort_order"]
        unique_together = [["school_class", "subject"]]

    def __str__(self) -> str:
        return f"{self.school_class} - {self.subject.code} (x{self.coefficient})"


class ClassCouncilRemark(models.Model):
    """Optional note (motif) for a class whose results are withheld.

    One row per class + period (term OR year). A class with a remark set has
    its statistics left blank in the class council report and the motif shown
    instead.
    """

    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="class_council_remarks"
    )
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.CASCADE, related_name="class_council_remarks"
    )
    academic_term = models.ForeignKey(
        AcademicTerm,
        on_delete=models.CASCADE,
        related_name="class_council_remarks",
        null=True,
        blank=True,
    )
    year_start = models.PositiveIntegerField(null=True, blank=True)
    year_end = models.PositiveIntegerField(null=True, blank=True)
    motif = models.TextField(blank=True)

    class Meta:
        verbose_name = "Class Council Remark"
        verbose_name_plural = "Class Council Remarks"
        ordering = ["school_class__sort_order"]

    def __str__(self) -> str:
        period = (
            f"T{self.academic_term.term_number}"
            if self.academic_term
            else f"{self.year_start}/{self.year_end}"
        )
        return f"{self.school_class} ({period}): {self.motif[:40]}"
