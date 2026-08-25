from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from .school import AcademicTerm, Competency, Subject
from .student import Student
from .teacher import Teacher


class CompetencyScore(models.Model):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="competency_scores"
    )
    competency = models.ForeignKey(
        Competency, on_delete=models.CASCADE, related_name="scores"
    )
    academic_term = models.ForeignKey(
        AcademicTerm, on_delete=models.CASCADE, related_name="competency_scores"
    )
    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(20)],
    )
    recorded_by = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL, null=True, blank=True
    )
    date_recorded = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Competency Score"
        verbose_name_plural = "Competency Scores"
        unique_together = [["student", "competency", "academic_term"]]

    def __str__(self) -> str:
        return f"{self.student} - {self.competency} - {self.score}/20"


class SubjectAverage(models.Model):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="subject_averages"
    )
    subject = models.ForeignKey(
        Subject, on_delete=models.CASCADE, related_name="subject_averages"
    )
    academic_term = models.ForeignKey(
        AcademicTerm, on_delete=models.CASCADE, related_name="subject_averages"
    )
    average = models.DecimalField(max_digits=5, decimal_places=2)
    grade = models.CharField(max_length=5, blank=True)
    remark = models.CharField(max_length=50, blank=True)

    class Meta:
        verbose_name = "Subject Average"
        verbose_name_plural = "Subject Averages"
        unique_together = [["student", "subject", "academic_term"]]

    def __str__(self) -> str:
        return f"{self.student} - {self.subject.code} - {self.average}"


class TermResult(models.Model):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="term_results"
    )
    academic_term = models.ForeignKey(
        AcademicTerm, on_delete=models.CASCADE, related_name="term_results"
    )
    total_score = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    total_coef = models.PositiveSmallIntegerField(default=0)
    average = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    rank = models.PositiveIntegerField(null=True, blank=True)
    grade = models.CharField(max_length=5, blank=True)
    remark = models.CharField(max_length=50, blank=True)
    remark_on_performance = models.TextField(blank=True)
    promoted = models.BooleanField(null=True, blank=True)

    class Meta:
        verbose_name = "Term Result"
        verbose_name_plural = "Term Results"
        unique_together = [["student", "academic_term"]]

    def __str__(self) -> str:
        return f"{self.student} - {self.academic_term} - AVG: {self.average}"
