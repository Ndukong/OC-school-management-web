from django.db import models

from .school import AcademicTerm, School, SchoolClass
from .student import Student
from .teacher import Teacher


class AttendanceRegister(models.Model):
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.CASCADE, related_name="attendance_registers"
    )
    date = models.DateField()
    period = models.PositiveSmallIntegerField(
        default=1, help_text="Period number within the day (1-based)."
    )
    recorded_by = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Attendance Register"
        verbose_name_plural = "Attendance Registers"
        unique_together = [["school_class", "date", "period"]]

    def __str__(self) -> str:
        return f"{self.school_class} - {self.date} (P{self.period})"


class AttendanceRecord(models.Model):
    STATUS_CHOICES = [
        ("P", "Present"),
        ("L", "Late"),
        ("A", "Absent"),
        ("PRM", "Permission"),
    ]

    register = models.ForeignKey(
        AttendanceRegister, on_delete=models.CASCADE, related_name="records"
    )
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="attendance_records"
    )
    status = models.CharField(max_length=3, choices=STATUS_CHOICES)

    class Meta:
        verbose_name = "Attendance Record"
        verbose_name_plural = "Attendance Records"
        unique_together = [["register", "student"]]

    def __str__(self) -> str:
        return f"{self.student} - {self.get_status_display()} ({self.register.date} P{self.register.period})"


class Punishment(models.Model):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="punishments"
    )
    academic_term = models.ForeignKey(
        AcademicTerm, on_delete=models.CASCADE, related_name="punishments"
    )
    hours = models.DecimalField(max_digits=5, decimal_places=1)
    reason = models.TextField()
    date_given = models.DateField()
    recorded_by = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        verbose_name = "Punishment"
        verbose_name_plural = "Punishments"

    def __str__(self) -> str:
        return f"{self.student} - {self.hours}h ({self.date_given})"


class ConductThreshold(models.Model):
    CONDUCT_CHOICES = [
        ("warning", "Conduct Warning"),
        ("reprimand", "Reprimand"),
        ("suspension", "Suspension"),
        ("dismissal", "Dismissal"),
    ]

    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="conduct_thresholds"
    )
    conduct_type = models.CharField(max_length=20, choices=CONDUCT_CHOICES, unique=True)
    min_unjustified_abs = models.PositiveIntegerField(default=0)
    min_justified_abs = models.PositiveIntegerField(default=0)
    min_lateness = models.PositiveIntegerField(default=0)
    min_punishment_hours = models.DecimalField(max_digits=5, decimal_places=1, default=0)

    class Meta:
        verbose_name = "Conduct Threshold"
        verbose_name_plural = "Conduct Thresholds"

    def __str__(self) -> str:
        return f"{self.get_conduct_type_display()} Threshold"


class DisciplineSummary(models.Model):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="discipline_summaries"
    )
    academic_term = models.ForeignKey(
        AcademicTerm, on_delete=models.CASCADE, related_name="discipline_summaries"
    )
    unjustified_abs_hours = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    justified_abs_hours = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    lateness_count = models.PositiveIntegerField(default=0)
    punishment_hours = models.DecimalField(max_digits=6, decimal_places=1, default=0)
    conduct_decision = models.CharField(
        max_length=20, choices=ConductThreshold.CONDUCT_CHOICES, blank=True
    )

    class Meta:
        verbose_name = "Discipline Summary"
        verbose_name_plural = "Discipline Summaries"
        unique_together = [["student", "academic_term"]]

    def __str__(self) -> str:
        return f"{self.student} - {self.academic_term} - {self.get_conduct_decision_display()}"
