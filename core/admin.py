from django.contrib import admin, messages

from core.utils.compute_results import compute_all_classes, compute_term_results

from .models import (
    AcademicTerm,
    AttendanceRecord,
    AttendanceRegister,
    ClassCouncilRemark,
    ClassSubject,
    Competency,
    CompetencyScore,
    ConductThreshold,
    DisciplineSummary,
    ExpenditureRecord,
    FeeType,
    FinanceSummary,
    IncomeRecord,
    PTADueConfig,
    PTARubricHead,
    PTARubricSubHead,
    Punishment,
    School,
    SchoolClass,
    Student,
    StudentEnrollment,
    Subject,
    SubjectAverage,
    Teacher,
    TeacherAssignment,
    TermResult,
    UserProfile,
)


@admin.action(description="Compute term results (current term) for selected classes")
def compute_class_results(modeladmin, request, queryset):
    for school_class in queryset:
        term = AcademicTerm.objects.filter(
            school=school_class.school, is_current=True
        ).first()
        if term is None:
            term = AcademicTerm.objects.filter(school=school_class.school).first()
        if term is None:
            messages.warning(
                request, f"No academic term configured for {school_class}."
            )
            continue
        stats = compute_term_results(school_class, term)
        messages.success(
            request,
            f"{school_class}: {stats['num_sat']} sat, {stats['num_passed']} passed, "
            f"class average {stats['class_average']}",
        )


@admin.action(description="Compute results for all classes (selected terms)")
def compute_term_results_action(modeladmin, request, queryset):
    for term in queryset:
        total_sat = 0
        total_passed = 0
        for stats in compute_all_classes(term):
            total_sat += stats["num_sat"]
            total_passed += stats["num_passed"]
        messages.success(
            request,
            f"{term}: {total_sat} sat, {total_passed} passed across all classes.",
        )


@admin.register(SchoolClass)
class SchoolClassAdmin(admin.ModelAdmin):
    actions = [compute_class_results]
    list_display = ["name", "code", "stream", "form_level", "sort_order"]


@admin.register(AcademicTerm)
class AcademicTermAdmin(admin.ModelAdmin):
    actions = [compute_term_results_action]
    list_display = ["term_number", "year_start", "year_end", "is_current"]


admin.site.register(School)
admin.site.register(Subject)
admin.site.register(Competency)
admin.site.register(ClassSubject)

admin.site.register(Student)
admin.site.register(StudentEnrollment)

admin.site.register(Teacher)
admin.site.register(TeacherAssignment)

admin.site.register(CompetencyScore)
admin.site.register(SubjectAverage)
admin.site.register(TermResult)

admin.site.register(AttendanceRegister)
admin.site.register(AttendanceRecord)
admin.site.register(Punishment)
admin.site.register(ConductThreshold)
admin.site.register(DisciplineSummary)

admin.site.register(ClassCouncilRemark)

admin.site.register(PTARubricHead)
admin.site.register(PTARubricSubHead)
admin.site.register(FeeType)
admin.site.register(PTADueConfig)
admin.site.register(IncomeRecord)
admin.site.register(ExpenditureRecord)
admin.site.register(FinanceSummary)

admin.site.register(UserProfile)
