from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from core.models import (
    AcademicTerm,
    FeeType,
    IncomeRecord,
    PTADueConfig,
    School,
    SchoolClass,
    Student,
    StudentEnrollment,
    UserProfile,
)


@pytest.fixture
def finance_data():
    school = School.objects.create(
        name_en="Finance School",
        matricule="FIN001",
        region_en="South West",
        division_en="Fako",
    )
    sc = SchoolClass.objects.create(
        school=school, name="Form 1", code="F1", form_level=1
    )
    term = AcademicTerm.objects.create(
        school=school, term_number=1, year_start=2025, year_end=2026, is_current=True
    )
    PTADueConfig.objects.create(school=school, school_class=sc, amount=Decimal(7000))

    pta_fee = FeeType.objects.create(school=school, name="PTA Due", category="PTA")
    state_fee = FeeType.objects.create(
        school=school, name="School Fees", category="state"
    )

    s1 = Student.objects.create(
        school=school,
        first_name="Alice",
        sex="F",
        unique_id="333111222",
        date_of_birth=date(2010, 1, 1),
        place_of_birth="Buea",
        guardian_name="G",
        division_of_origin="Fako",
        region_of_origin="South West",
    )
    s2 = Student.objects.create(
        school=school,
        first_name="Bob",
        sex="M",
        unique_id="333222333",
        date_of_birth=date(2009, 1, 1),
        place_of_birth="Buea",
        guardian_name="G",
        division_of_origin="Fako",
        region_of_origin="South West",
    )
    StudentEnrollment.objects.create(student=s1, school_class=sc, academic_term=term)
    StudentEnrollment.objects.create(student=s2, school_class=sc, academic_term=term)

    # Alice paid 3000 PTA, Bob paid 2500 PTA, plus 1000 state income.
    # Amounts are deliberately distinct so dashboard totals cannot mask
    # each other: expected 14000, collected 5500, outstanding 8500.
    IncomeRecord.objects.create(
        school=school,
        academic_term=term,
        fee_type=pta_fee,
        student=s1,
        amount=Decimal(3000),
        date_paid=date(2025, 10, 1),
        receipt_number="R001",
    )
    IncomeRecord.objects.create(
        school=school,
        academic_term=term,
        fee_type=pta_fee,
        student=s2,
        amount=Decimal(2500),
        date_paid=date(2025, 10, 2),
        receipt_number="R002",
    )
    IncomeRecord.objects.create(
        school=school,
        academic_term=term,
        fee_type=state_fee,
        amount=Decimal(1000),
        date_paid=date(2025, 10, 3),
        receipt_number="R003",
    )

    def make_user(username, role, is_superuser=False):
        user = User.objects.create_user(
            username=username, password="pass", is_superuser=is_superuser
        )
        UserProfile.objects.create(user=user, school=school, role=role)
        return user

    bursar = make_user("bursar1", "bursar")
    teacher = make_user("teacher1", "teacher")
    admin = make_user("admin1", "admin", is_superuser=True)

    def login(user):
        c = Client()
        c.login(username=user.username, password="pass")
        return c

    return {
        "school": school,
        "school_class": sc,
        "term": term,
        "s1": s1,
        "s2": s2,
        "pta_fee": pta_fee,
        "state_fee": state_fee,
        "bursar": bursar,
        "teacher": teacher,
        "admin": admin,
        "login": login,
    }


@pytest.mark.django_db
class TestFinanceDashboard:
    def test_bursar_can_access_dashboard(self, finance_data):
        c = finance_data["login"](finance_data["bursar"])
        r = c.get(reverse("finance_dashboard"))
        assert r.status_code == 200
        html = r.content.decode()
        assert "Income vs Expenditure" in html
        assert "PTA Collection" in html

    def test_teacher_cannot_access_dashboard(self, finance_data):
        c = finance_data["login"](finance_data["teacher"])
        r = c.get(reverse("finance_dashboard"))
        assert r.status_code == 403

    def test_expected_collected_outstanding_by_class(self, finance_data):
        c = finance_data["login"](finance_data["bursar"])
        r = c.get(reverse("finance_dashboard"))
        html = r.content.decode().replace(",", "")
        # Expected = 7000 x 2 enrolled = 14000
        assert "14000" in html
        # Collected PTA = 3000 + 2500 = 5500
        assert "5500" in html
        # Outstanding = 14000 - 5500 = 8500
        assert "8500" in html

    def test_income_and_expenditure_forms_post(self, finance_data):
        c = finance_data["login"](finance_data["bursar"])
        # Income
        r = c.post(
            reverse("finance_dashboard"),
            {
                "form_type": "income",
                "fee_type": finance_data["pta_fee"].id,
                "student": finance_data["s1"].id,
                "amount": "1500",
                "date_paid": "2025-11-01",
                "receipt_number": "R004",
            },
        )
        assert r.status_code == 302
        assert IncomeRecord.objects.filter(receipt_number="R004").count() == 1

    def test_admin_can_post_expenditure(self, finance_data):
        c = finance_data["login"](finance_data["admin"])
        r = c.post(
            reverse("finance_dashboard"),
            {
                "form_type": "expenditure",
                "category": "PTA",
                "amount": "500",
                "date": "2025-11-02",
                "description": "Chairs",
            },
        )
        assert r.status_code == 302
        from core.models import ExpenditureRecord

        assert ExpenditureRecord.objects.filter(description="Chairs").count() == 1


@pytest.mark.django_db
class TestStudentFeeStatus:
    def test_student_fee_status_renders(self, finance_data):
        c = finance_data["login"](finance_data["bursar"])
        r = c.get(reverse("student_fee_status", args=[finance_data["s1"].id]))
        assert r.status_code == 200
        html = r.content.decode()
        assert "Fee Status" in html
        assert "Alice" in html
        # Alice paid 3000
        assert "3000" in html

    def test_student_fee_status_outstanding(self, finance_data):
        c = finance_data["login"](finance_data["bursar"])
        r = c.get(reverse("student_fee_status", args=[finance_data["s1"].id]))
        html = r.content.decode()
        # Expected 7000, paid 3000 -> outstanding 4000 (distinct from both)
        assert "4000" in html

    def test_teacher_cannot_view_fee_status(self, finance_data):
        c = finance_data["login"](finance_data["teacher"])
        r = c.get(reverse("student_fee_status", args=[finance_data["s1"].id]))
        assert r.status_code == 403

    def test_student_fee_status_immutable_note(self, finance_data):
        c = finance_data["login"](finance_data["bursar"])
        r = c.get(reverse("student_fee_status", args=[finance_data["s1"].id]))
        html = r.content.decode()
        assert "immutable" in html.lower()

    def test_income_record_creates_audit_log(self, finance_data):
        from auditlog.models import LogEntry
        from django.contrib.contenttypes.models import ContentType

        c = finance_data["login"](finance_data["bursar"])
        r = c.post(
            reverse("finance_dashboard"),
            {
                "form_type": "income",
                "fee_type": finance_data["pta_fee"].id,
                "student": finance_data["s1"].id,
                "amount": "750",
                "date_paid": "2025-12-01",
                "receipt_number": "RAUDIT1",
            },
        )
        assert r.status_code == 302
        record = IncomeRecord.objects.get(receipt_number="RAUDIT1")
        ct = ContentType.objects.get_for_model(IncomeRecord)
        assert (
            LogEntry.objects.filter(content_type=ct, object_pk=str(record.pk)).count()
            == 1
        )
        assert record.created_at is not None

    def test_no_delete_or_update_endpoints_for_transactions(self, finance_data):
        from django.urls import get_resolver

        patterns = get_resolver().url_patterns
        finance_paths = []
        for p in patterns:
            if hasattr(p, "url_patterns"):
                for sub in p.url_patterns:
                    if (
                        "finance" in str(sub.pattern)
                        or "income" in str(sub.pattern)
                        or "expenditure" in str(sub.pattern)
                    ):
                        finance_paths.append(str(sub.pattern))
        for fp in finance_paths:
            assert "delete" not in fp.lower()
            assert "edit" not in fp.lower()
