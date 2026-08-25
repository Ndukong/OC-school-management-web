from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from core.models import (
    AcademicTerm,
    ExpenditureRecord,
    FeeType,
    FinanceSummary,
    IncomeRecord,
    PTARubricHead,
    PTARubricSubHead,
    School,
    SchoolClass,
    UserProfile,
)
from core.utils.finance import get_finance_totals, recompute_finance_summary


@pytest.fixture
def school_data():
    school = School.objects.create(
        name_en="Test School",
        matricule="TEST001",
        region_en="South West",
        division_en="Fako",
    )
    school_class = SchoolClass.objects.create(
        school=school, name="Form 1", code="F1", form_level=1
    )
    term = AcademicTerm.objects.create(
        school=school, term_number=1, year_start=2025, year_end=2026, is_current=True
    )
    return {"school": school, "school_class": school_class, "term": term}


def make_user(username, school, role, password="pass"):
    user = User.objects.create_user(username=username, password=password)
    UserProfile.objects.create(user=user, school=school, role=role)
    return user


def make_fee(school, name, category):
    return FeeType.objects.create(school=school, name=name, category=category)


@pytest.mark.django_db
class TestFinanceTotals:
    def test_totals_split_by_category(self, school_data):
        data = school_data
        pta = make_fee(data["school"], "PTA Due", "PTA")
        state = make_fee(data["school"], "School Fees", "state")
        IncomeRecord.objects.create(
            school=data["school"],
            fee_type=pta,
            amount=Decimal(5000),
            date_paid=date(2025, 10, 1),
            academic_term=data["term"],
        )
        IncomeRecord.objects.create(
            school=data["school"],
            fee_type=state,
            amount=Decimal(2000),
            date_paid=date(2025, 10, 2),
            academic_term=data["term"],
        )
        ExpenditureRecord.objects.create(
            school=data["school"],
            category="PTA",
            amount=Decimal(1500),
            date=date(2025, 10, 3),
            academic_term=data["term"],
        )
        ExpenditureRecord.objects.create(
            school=data["school"],
            category="state",
            amount=Decimal(500),
            date=date(2025, 10, 4),
            academic_term=data["term"],
        )

        totals = get_finance_totals(data["school"], data["term"])

        assert totals["total_pta_income"] == Decimal(5000)
        assert totals["total_state_income"] == Decimal(2000)
        assert totals["total_income"] == Decimal(7000)
        assert totals["total_pta_expenditure"] == Decimal(1500)
        assert totals["total_state_expenditure"] == Decimal(500)
        assert totals["total_expenditure"] == Decimal(2000)
        assert totals["balance"] == Decimal(5000)
        assert totals["pta_balance"] == Decimal(3500)
        assert totals["state_balance"] == Decimal(1500)

    def test_recompute_finance_summary_persists(self, school_data):
        data = school_data
        pta = make_fee(data["school"], "PTA Due", "PTA")
        IncomeRecord.objects.create(
            school=data["school"],
            fee_type=pta,
            amount=Decimal(3000),
            date_paid=date(2025, 10, 1),
            academic_term=data["term"],
        )

        summary = recompute_finance_summary(data["school"], data["term"])

        assert FinanceSummary.objects.count() == 1
        assert summary.total_pta_income == Decimal(3000)
        assert summary.total_state_income == Decimal(0)

        recompute_finance_summary(data["school"], data["term"])
        assert FinanceSummary.objects.count() == 1


@pytest.mark.django_db
class TestFinanceDashboardAccess:
    def test_teacher_forbidden(self, school_data):
        make_user("teacher1", school_data["school"], "teacher")
        c = Client()
        c.login(username="teacher1", password="pass")
        assert c.get(reverse("finance_dashboard")).status_code == 403

    def test_bursar_allowed(self, school_data):
        make_user("bursar1", school_data["school"], "bursar")
        c = Client()
        c.login(username="bursar1", password="pass")
        assert c.get(reverse("finance_dashboard")).status_code == 200

    def test_admin_allowed(self, school_data):
        make_user("admin", school_data["school"], "admin")
        c = Client()
        c.login(username="admin", password="pass")
        assert c.get(reverse("finance_dashboard")).status_code == 200


@pytest.mark.django_db
class TestFinanceEntry:
    def test_post_income_creates_record_and_summary(self, school_data):
        data = school_data
        make_user("bursar1", data["school"], "bursar")
        pta = make_fee(data["school"], "PTA Due", "PTA")
        c = Client()
        c.login(username="bursar1", password="pass")

        response = c.post(
            reverse("finance_dashboard"),
            {
                "form_type": "income",
                "fee_type": pta.id,
                "amount": "2500.50",
                "date_paid": "2025-10-05",
                "receipt_number": "R-001",
                "notes": "",
            },
        )

        assert response.status_code == 302
        record = IncomeRecord.objects.get()
        assert record.amount == Decimal("2500.50")
        assert record.academic_term == data["term"]
        summary = FinanceSummary.objects.get()
        assert summary.total_pta_income == Decimal("2500.50")

    def test_post_expenditure_creates_record(self, school_data):
        data = school_data
        make_user("bursar1", data["school"], "bursar")
        head = PTARubricHead.objects.create(school=data["school"], name="Rent")
        sub = PTARubricSubHead.objects.create(rubric_head=head, name="Hall")
        c = Client()
        c.login(username="bursar1", password="pass")

        response = c.post(
            reverse("finance_dashboard"),
            {
                "form_type": "expenditure",
                "category": "PTA",
                "rubric_sub_head": sub.id,
                "amount": "800",
                "date": "2025-10-06",
                "description": "Hall maintenance",
            },
        )

        assert response.status_code == 302
        record = ExpenditureRecord.objects.get()
        assert record.category == "PTA"
        assert record.amount == Decimal(800)
        assert record.rubric_sub_head == sub

    def test_invalid_income_form_does_not_save(self, school_data):
        data = school_data
        make_user("bursar1", data["school"], "bursar")
        pta = make_fee(data["school"], "PTA Due", "PTA")
        c = Client()
        c.login(username="bursar1", password="pass")

        response = c.post(
            reverse("finance_dashboard"),
            {
                "form_type": "income",
                "fee_type": pta.id,
                "amount": "0",
                "date_paid": "2025-10-05",
            },
        )

        assert response.status_code == 200
        assert IncomeRecord.objects.count() == 0
