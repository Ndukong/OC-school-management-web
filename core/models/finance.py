from auditlog.registry import auditlog
from django.db import models

from .school import AcademicTerm, School, SchoolClass
from .student import Student
from .teacher import Teacher


class PTARubricHead(models.Model):
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="pta_rubric_heads"
    )
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=10, blank=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "PTA Rubric Head"
        verbose_name_plural = "PTA Rubric Heads"
        ordering = ["sort_order"]
        unique_together = [["school", "code"]]

    def __str__(self) -> str:
        return self.name


class PTARubricSubHead(models.Model):
    rubric_head = models.ForeignKey(
        PTARubricHead, on_delete=models.CASCADE, related_name="sub_heads"
    )
    name = models.CharField(max_length=255)
    code = models.CharField(max_length=10, blank=True)

    class Meta:
        verbose_name = "PTA Rubric Sub-Head"
        verbose_name_plural = "PTA Rubric Sub-Heads"

    def __str__(self) -> str:
        return f"{self.rubric_head.name} - {self.name}"


class FeeType(models.Model):
    CATEGORY_CHOICES = [("PTA", "PTA"), ("state", "State")]

    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="fee_types"
    )
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Fee Type"
        verbose_name_plural = "Fee Types"

    def __str__(self) -> str:
        return f"[{self.get_category_display()}] {self.name}"


class PTADueConfig(models.Model):
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="pta_due_configs"
    )
    school_class = models.ForeignKey(
        SchoolClass, on_delete=models.CASCADE, related_name="pta_due_configs"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "PTA Due Config"
        verbose_name_plural = "PTA Due Configs"
        unique_together = [["school", "school_class"]]

    def __str__(self) -> str:
        return f"{self.school_class} - {self.amount} FCFA"


class IncomeRecord(models.Model):
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="income_records"
    )
    fee_type = models.ForeignKey(
        FeeType, on_delete=models.SET_NULL, null=True, related_name="income_records"
    )
    student = models.ForeignKey(
        Student, on_delete=models.SET_NULL, null=True, blank=True, related_name="income_records"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date_paid = models.DateField()
    receipt_number = models.CharField(max_length=50, blank=True)
    academic_term = models.ForeignKey(
        AcademicTerm, on_delete=models.SET_NULL, null=True, blank=True
    )
    recorded_by = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL, null=True, blank=True
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Income Record"
        verbose_name_plural = "Income Records"
        ordering = ["-date_paid"]

    def __str__(self) -> str:
        return f"{self.fee_type} - {self.amount} FCFA ({self.date_paid})"


class ExpenditureRecord(models.Model):
    CATEGORY_CHOICES = [("PTA", "PTA"), ("state", "State")]

    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="expenditure_records"
    )
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES)
    rubric_sub_head = models.ForeignKey(
        PTARubricSubHead, on_delete=models.SET_NULL, null=True, blank=True, related_name="expenditure_records"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField()
    description = models.TextField(blank=True)
    academic_term = models.ForeignKey(
        AcademicTerm, on_delete=models.SET_NULL, null=True, blank=True
    )
    recorded_by = models.ForeignKey(
        Teacher, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Expenditure Record"
        verbose_name_plural = "Expenditure Records"
        ordering = ["-date"]

    def __str__(self) -> str:
        return f"{self.get_category_display()} - {self.amount} FCFA ({self.date})"


class FinanceSummary(models.Model):
    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="finance_summaries"
    )
    academic_term = models.ForeignKey(
        AcademicTerm, on_delete=models.CASCADE, related_name="finance_summaries"
    )
    total_pta_income = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_pta_expenditure = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_state_income = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    total_state_expenditure = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Finance Summary"
        verbose_name_plural = "Finance Summaries"
        unique_together = [["school", "academic_term"]]

    def __str__(self) -> str:
        return f"{self.school} - {self.academic_term}"


auditlog.register(IncomeRecord)
auditlog.register(ExpenditureRecord)
auditlog.register(FinanceSummary)
