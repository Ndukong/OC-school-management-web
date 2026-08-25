from decimal import Decimal

from django.db.models import Sum

from core.models import ExpenditureRecord, FinanceSummary, IncomeRecord


def _sum_amount(qs) -> Decimal:
    return qs.aggregate(total=Sum("amount"))["total"] or Decimal(0)


def get_finance_totals(school, term=None) -> dict:
    """Aggregate income/expenditure totals for a school, optionally per term."""
    incomes = IncomeRecord.objects.filter(school=school)
    expenditures = ExpenditureRecord.objects.filter(school=school)
    if term is not None:
        incomes = incomes.filter(academic_term=term)
        expenditures = expenditures.filter(academic_term=term)

    total_pta_income = _sum_amount(incomes.filter(fee_type__category="PTA"))
    total_state_income = _sum_amount(incomes.filter(fee_type__category="state"))
    total_pta_expenditure = _sum_amount(expenditures.filter(category="PTA"))
    total_state_expenditure = _sum_amount(expenditures.filter(category="state"))
    total_income = total_pta_income + total_state_income
    total_expenditure = total_pta_expenditure + total_state_expenditure

    return {
        "total_pta_income": total_pta_income,
        "total_state_income": total_state_income,
        "total_income": total_income,
        "total_pta_expenditure": total_pta_expenditure,
        "total_state_expenditure": total_state_expenditure,
        "total_expenditure": total_expenditure,
        "balance": total_income - total_expenditure,
        "pta_balance": total_pta_income - total_pta_expenditure,
        "state_balance": total_state_income - total_state_expenditure,
    }


def recompute_finance_summary(school, term) -> FinanceSummary:
    """Upsert the stored FinanceSummary row for a school/term from live records."""
    totals = get_finance_totals(school, term)
    summary, _ = FinanceSummary.objects.update_or_create(
        school=school,
        academic_term=term,
        defaults={
            "total_pta_income": totals["total_pta_income"],
            "total_pta_expenditure": totals["total_pta_expenditure"],
            "total_state_income": totals["total_state_income"],
            "total_state_expenditure": totals["total_state_expenditure"],
        },
    )
    return summary
