from decimal import Decimal

from django.db.models import Sum

from core.models import AcademicTerm, ExpenditureRecord, FeeType, IncomeRecord, School
from core.utils.finance import get_finance_totals
from core.utils.reports import BaseReport


class PTAFinanceReport(BaseReport):
    template_name = "reports/pta_finance.html"
    css_files = ["reports/css/report.css"]

    def __init__(self, term: AcademicTerm, school: School):
        self.term = term
        self.school = school

    def get_context_data(self) -> dict:
        totals = get_finance_totals(self.school, self.term)

        fee_breakdown = []
        for ft in FeeType.objects.filter(school=self.school).order_by(
            "category", "name"
        ):
            total = IncomeRecord.objects.filter(
                school=self.school, academic_term=self.term, fee_type=ft
            ).aggregate(total=Sum("amount"))["total"] or Decimal(0)
            if total > 0:
                fee_breakdown.append({"fee_type": ft, "total": total})

        incomes = list(
            IncomeRecord.objects.filter(school=self.school, academic_term=self.term)
            .select_related("fee_type")
            .order_by("-date_paid")
        )
        expenditures = list(
            ExpenditureRecord.objects.filter(
                school=self.school, academic_term=self.term
            ).order_by("-date")
        )

        return {
            "school": self.school,
            "term": self.term,
            "totals": totals,
            "fee_breakdown": fee_breakdown,
            "incomes": incomes,
            "expenditures": expenditures,
        }

    def filename(self) -> str:
        return f"pta_finance_report_{self.term}.pdf"
