from decimal import Decimal

from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from core.forms import ExpenditureRecordForm, IncomeRecordForm
from core.models import (
    AcademicTerm,
    ExpenditureRecord,
    IncomeRecord,
    PTADueConfig,
    SchoolClass,
    Student,
    StudentEnrollment,
)
from core.utils.finance import get_finance_totals, recompute_finance_summary
from core.utils.permissions import (
    get_school_for_user,
    get_teacher_for_user,
    role_required,
)


def _class_fee_breakdown(school, term):
    """Expected / collected / outstanding per class for the current term."""
    rows = []
    classes = SchoolClass.objects.filter(school=school).order_by("sort_order")
    for sc in classes:
        due = PTADueConfig.objects.filter(school=school, school_class=sc).first()
        if not due:
            continue
        student_ids = StudentEnrollment.objects.filter(
            school_class=sc, academic_term=term
        ).values_list("student_id", flat=True)
        enrolled = len(list(student_ids))
        expected = due.amount * Decimal(enrolled)
        collected = (
            IncomeRecord.objects.filter(
                school=school,
                academic_term=term,
                fee_type__category="PTA",
                student_id__in=list(student_ids),
            ).aggregate(total=Sum("amount"))["total"]
            or Decimal(0)
        )
        rows.append(
            {
                "school_class": sc,
                "enrolled": enrolled,
                "due": due.amount,
                "expected": expected,
                "collected": collected,
                "outstanding": max(expected - collected, Decimal(0)),
            }
        )
    return rows


def _chart_data(school, term):
    """Income vs expenditure per category for the chart."""
    pta_income = (
        IncomeRecord.objects.filter(
            school=school, academic_term=term, fee_type__category="PTA"
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal(0)
    )
    state_income = (
        IncomeRecord.objects.filter(
            school=school, academic_term=term, fee_type__category="state"
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal(0)
    )
    pta_exp = (
        ExpenditureRecord.objects.filter(
            school=school, academic_term=term, category="PTA"
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal(0)
    )
    state_exp = (
        ExpenditureRecord.objects.filter(
            school=school, academic_term=term, category="state"
        ).aggregate(total=Sum("amount"))["total"]
        or Decimal(0)
    )
    max_value = max(pta_income, state_income, pta_exp, state_exp, Decimal(1))
    return {
        "pta_income": pta_income,
        "state_income": state_income,
        "pta_exp": pta_exp,
        "state_exp": state_exp,
        "max_value": max_value,
    }


@role_required("admin", "bursar")
def finance_dashboard(request):
    school = get_school_for_user(request.user)
    if not school:
        messages.error(request, "No school linked to your account.")
        return redirect("teacher_dashboard")

    term = AcademicTerm.objects.filter(school=school, is_current=True).first()
    if not term:
        term = AcademicTerm.objects.filter(school=school).first()

    teacher = get_teacher_for_user(request.user)

    if request.method == "POST":
        form_type = request.POST.get("form_type")
        if form_type == "income":
            form = IncomeRecordForm(request.POST, school=school)
            if form.is_valid():
                IncomeRecord.objects.create(
                    school=school,
                    academic_term=term,
                    recorded_by=teacher,
                    **form.cleaned_data,
                )
                recompute_finance_summary(school, term)
                messages.success(request, "Income recorded.")
                return redirect("finance_dashboard")
            messages.error(request, "Income form is invalid.")
        elif form_type == "expenditure":
            form = ExpenditureRecordForm(request.POST, school=school)
            if form.is_valid():
                ExpenditureRecord.objects.create(
                    school=school,
                    academic_term=term,
                    recorded_by=teacher,
                    **form.cleaned_data,
                )
                recompute_finance_summary(school, term)
                messages.success(request, "Expenditure recorded.")
                return redirect("finance_dashboard")
            messages.error(request, "Expenditure form is invalid.")

    income_form = IncomeRecordForm(school=school)
    expenditure_form = ExpenditureRecordForm(school=school)

    totals = get_finance_totals(school, term)
    recent_income = IncomeRecord.objects.filter(school=school).select_related(
        "fee_type", "student"
    )[:10]
    recent_expenditure = ExpenditureRecord.objects.filter(school=school).select_related(
        "rubric_sub_head"
    )[:10]

    breakdown = _class_fee_breakdown(school, term) if term else []
    chart = _chart_data(school, term) if term else None
    total_expected = sum((b["expected"] for b in breakdown), Decimal(0))
    total_collected = sum((b["collected"] for b in breakdown), Decimal(0))
    total_outstanding = sum((b["outstanding"] for b in breakdown), Decimal(0))

    return render(
        request,
        "finance/dashboard.html",
        {
            "school": school,
            "term": term,
            "totals": totals,
            "recent_income": recent_income,
            "recent_expenditure": recent_expenditure,
            "income_form": income_form,
            "expenditure_form": expenditure_form,
            "breakdown": breakdown,
            "chart": chart,
            "total_expected": total_expected,
            "total_collected": total_collected,
            "total_outstanding": total_outstanding,
        },
    )


@role_required("admin", "bursar")
def student_fee_status(request, student_id: int):
    school = get_school_for_user(request.user)
    student = get_object_or_404(Student, pk=student_id)
    if school and student.school_id != school.pk:
        messages.error(request, "Student not found.")
        return redirect("finance_dashboard")

    terms = AcademicTerm.objects.filter(school=student.school).order_by(
        "-year_start", "-year_end", "term_number"
    )
    term_id = request.GET.get("term_id")
    if term_id:
        term = get_object_or_404(AcademicTerm, pk=term_id)
    else:
        term = terms.filter(is_current=True).first() or terms.first()

    payments = (
        IncomeRecord.objects.filter(school=student.school, student=student)
        .select_related("fee_type")
        .order_by("-date_paid")
    )
    if term:
        payments = payments.filter(academic_term=term)

    collected = payments.aggregate(total=Sum("amount"))["total"] or Decimal(0)

    expected = Decimal(0)
    if term:
        enrollment = student.enrollments.filter(academic_term=term).first()
        if enrollment:
            due = PTADueConfig.objects.filter(
                school=student.school, school_class=enrollment.school_class
            ).first()
            if due:
                expected = due.amount

    return render(
        request,
        "finance/student_status.html",
        {
            "student": student,
            "term": term,
            "terms": terms,
            "payments": payments,
            "collected": collected,
            "expected": expected,
            "outstanding": max(expected - collected, Decimal(0)),
        },
    )
