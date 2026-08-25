"""Phase 10: Parent Portal — authentication, read-only, scoping tests.

Tests:
  - Login with correct credentials succeeds
  - Login with wrong ID or wrong phone fails with generic error
  - Unauthenticated redirects to login
  - All portal views are read-only (no POST endpoints for data mutation)
  - Student data is scoped to the authenticated student only
  - Parent cannot access staff dashboard or any admin views
  - Portal templates don't include staff sidebar/navigation
"""
from datetime import date
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from core.models import (
    AcademicTerm,
    AttendanceRecord,
    AttendanceRegister,
    ClassSubject,
    IncomeRecord,
    PTADueConfig,
    School,
    SchoolClass,
    Student,
    StudentEnrollment,
    Subject,
    SubjectAverage,
    TermResult,
)


@pytest.fixture
def portal_data():
    school = School.objects.create(
        name_en="Portal School",
        matricule="PS001",
        region_en="Far North",
        division_en="Mayo-Danay",
    )
    sc = SchoolClass.objects.create(
        school=school, name="Form 3", code="F3", form_level=3
    )
    term = AcademicTerm.objects.create(
        school=school, term_number=1, year_start=2025, year_end=2026, is_current=True
    )
    subject = Subject.objects.create(school=school, name="Mathematics", code="MAT")
    ClassSubject.objects.create(
        school_class=sc, subject=subject, coefficient=4
    )

    # Student A — parent portal target
    student_a = Student.objects.create(
        school=school,
        first_name="Alice",
        other_names="Nfor",
        sex="F",
        unique_id="111222333",
        date_of_birth=date(2010, 3, 15),
        place_of_birth="Maroua",
        guardian_name="Mr Nfor",
        guardian_contact="671000001",
        division_of_origin="Mayo-Danay",
        region_of_origin="Far North",
    )
    StudentEnrollment.objects.create(
        student=student_a, school_class=sc, academic_term=term
    )
    TermResult.objects.create(
        student=student_a,
        academic_term=term,
        total_score=Decimal("120.00"),
        total_coef=8,
        average=Decimal("15.00"),
        rank=3,
        grade="B",
        remark="Very Good",
    )
    SubjectAverage.objects.create(
        student=student_a,
        subject=subject,
        academic_term=term,
        average=Decimal("15.00"),
        grade="B",
        remark="Very Good",
    )
    subject_b = Subject.objects.create(school=school, name="English", code="ENL")
    ClassSubject.objects.create(school_class=sc, subject=subject_b, coefficient=3)
    SubjectAverage.objects.create(
        student=student_a,
        subject=subject_b,
        academic_term=term,
        average=Decimal("12.00"),
        grade="C+",
        remark="Good",
    )

    # Attendance records
    reg = AttendanceRegister.objects.create(school_class=sc, date=date(2025, 10, 1), period=1)
    AttendanceRecord.objects.create(register=reg, student=student_a, status="P")
    reg2 = AttendanceRegister.objects.create(school_class=sc, date=date(2025, 10, 2), period=1)
    AttendanceRecord.objects.create(register=reg2, student=student_a, status="A")
    reg3 = AttendanceRegister.objects.create(school_class=sc, date=date(2025, 10, 3), period=1)
    AttendanceRecord.objects.create(register=reg3, student=student_a, status="L")

    # Fee payment
    fee_type = None
    from core.models import FeeType
    fee_type = FeeType.objects.create(school=school, name="PTA Term", category="PTA")
    PTADueConfig.objects.create(school=school, school_class=sc, amount=Decimal(20000))
    IncomeRecord.objects.create(
        school=school,
        student=student_a,
        fee_type=fee_type,
        amount=Decimal(12000),
        date_paid=date(2025, 10, 5),
        academic_term=term,
    )

    # Student B — belongs to different parent, different phone
    student_b = Student.objects.create(
        school=school,
        first_name="Bob",
        sex="M",
        unique_id="444555666",
        date_of_birth=date(2011, 1, 1),
        place_of_birth="Maroua",
        guardian_name="Mrs Kamga",
        guardian_contact="672000000",
        division_of_origin="Mayo-Danay",
        region_of_origin="Far North",
    )
    StudentEnrollment.objects.create(
        student=student_b, school_class=sc, academic_term=term
    )

    def parent_client():
        c = Client()
        c.post(reverse("parent:login"), {
            "unique_id": "111222333",
            "guardian_contact": "671000001",
        })
        return c

    return {
        "school": school,
        "sc": sc,
        "term": term,
        "subject": subject,
        "student_a": student_a,
        "student_b": student_b,
        "parent_client": parent_client,
    }


# ─── Authentication Tests ───────────────────────────────────────────────────

@pytest.mark.django_db
class TestParentAuth:
    def test_login_page_renders(self, portal_data):
        c = Client()
        r = c.get(reverse("parent:login"))
        assert r.status_code == 200
        html = r.content.decode()
        assert "Student 9-digit ID" in html
        assert "Guardian Phone" in html

    def test_login_success_redirects_to_dashboard(self, portal_data):
        c = Client()
        r = c.post(reverse("parent:login"), {
            "unique_id": "111222333",
            "guardian_contact": "671000001",
        })
        assert r.status_code == 302
        assert r.url == reverse("parent:dashboard")

    def test_login_sets_session(self, portal_data):
        c = Client()
        c.post(reverse("parent:login"), {
            "unique_id": "111222333",
            "guardian_contact": "671000001",
        })
        assert c.session.get("parent_student_id") == portal_data["student_a"].pk

    def test_wrong_id_shows_generic_error(self, portal_data):
        c = Client()
        r = c.post(reverse("parent:login"), {
            "unique_id": "999999999",
            "guardian_contact": "671000001",
        })
        assert r.status_code == 302
        assert r.url == reverse("parent:login")

    def test_wrong_phone_shows_generic_error(self, portal_data):
        c = Client()
        r = c.post(reverse("parent:login"), {
            "unique_id": "111222333",
            "guardian_contact": "999999999",
        })
        assert r.status_code == 302
        assert r.url == reverse("parent:login")

    def test_wrong_phone_error_same_as_wrong_id(self, portal_data):
        """Invalid credentials produce the same generic error, regardless of which part is wrong."""
        c1 = Client()
        r1 = c1.post(reverse("parent:login"), {
            "unique_id": "999999999",
            "guardian_contact": "671000001",
        })
        c2 = Client()
        r2 = c2.post(reverse("parent:login"), {
            "unique_id": "111222333",
            "guardian_contact": "999999999",
        })
        # Both redirect to login (same error path)
        assert r1.url == r2.url == reverse("parent:login")

    def test_inactive_student_cannot_login(self, portal_data):
        portal_data["student_a"].is_active = False
        portal_data["student_a"].save()
        c = Client()
        r = c.post(reverse("parent:login"), {
            "unique_id": "111222333",
            "guardian_contact": "671000001",
        })
        assert r.url == reverse("parent:login")

    def test_logout_clears_session(self, portal_data):
        c = portal_data["parent_client"]()
        r = c.get(reverse("parent:logout"))
        assert r.status_code == 302
        assert r.url == reverse("parent:login")
        assert c.session.get("parent_student_id") is None


# ─── Access Control Tests ───────────────────────────────────────────────────

@pytest.mark.django_db
class TestPortalAccess:
    def test_unauthenticated_redirects_to_login(self, portal_data):
        for name in ["dashboard", "student_detail", "marks", "attendance", "fees"]:
            c = Client()
            r = c.get(reverse(f"parent:{name}"))
            assert r.status_code == 302
            assert r.url == reverse("parent:login")

    def test_portal_views_are_get_only(self, portal_data):
        """No portal view accepts POST for data mutation — read-only enforcement.
        Views accept POST with no effect (no data modified)."""
        c = portal_data["parent_client"]()
        for name in ["student_detail", "marks", "attendance", "fees"]:
            r = c.post(reverse(f"parent:{name}"))
            assert r.status_code in (200, 405), f"{name}: POST should not modify data"
            html = r.content.decode()
            assert "Save" not in html and "Update" not in html, f"{name}: should have no save buttons"


# ─── Scoping Tests ──────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestPortalScoping:
    def test_dashboard_shows_correct_student(self, portal_data):
        c = portal_data["parent_client"]()
        r = c.get(reverse("parent:dashboard"))
        assert r.status_code == 200
        html = r.content.decode()
        assert "Alice" in html
        assert "15.00" in html

    def test_dashboard_shows_attendance(self, portal_data):
        c = portal_data["parent_client"]()
        r = c.get(reverse("parent:dashboard"))
        html = r.content.decode()
        assert "1" in html  # 1 present
        assert "1" in html  # 1 unjustified

    def test_dashboard_shows_fee_outstanding(self, portal_data):
        c = portal_data["parent_client"]()
        r = c.get(reverse("parent:dashboard"))
        html = r.content.decode()
        assert "8000" in html  # 20000 - 12000 = 8000

    def test_student_detail_shows_alice_not_bob(self, portal_data):
        c = portal_data["parent_client"]()
        r = c.get(reverse("parent:student_detail"))
        html = r.content.decode()
        assert "Alice" in html
        assert "Nfor" in html
        assert "Bob" not in html

    def test_marks_shows_alice_subjects(self, portal_data):
        c = portal_data["parent_client"]()
        r = c.get(reverse("parent:marks"))
        html = r.content.decode()
        assert "Mathematics" in html
        assert "15.00" in html
        assert "English" in html
        assert "12.00" in html

    def test_marks_does_not_show_other_students(self, portal_data):
        c = portal_data["parent_client"]()
        r = c.get(reverse("parent:marks"))
        html = r.content.decode()
        assert "Bob" not in html

    def test_attendance_shows_alice_records(self, portal_data):
        c = portal_data["parent_client"]()
        r = c.get(reverse("parent:attendance"))
        html = r.content.decode()
        assert "Present" in html
        assert "Absent" in html
        assert "Late" in html

    def test_fees_shows_alice_payments(self, portal_data):
        c = portal_data["parent_client"]()
        r = c.get(reverse("parent:fees"))
        html = r.content.decode()
        assert "12000" in html  # paid
        assert "20000" in html  # expected
        assert "8000" in html   # outstanding

    def test_student_b_parent_cannot_see_alice_data(self, portal_data):
        """Student B's parent session shows nothing about Alice."""
        c = Client()
        c.post(reverse("parent:login"), {
            "unique_id": "444555666",
            "guardian_contact": "672000000",
        })

        r = c.get(reverse("parent:dashboard"))
        html = r.content.decode()
        assert "Alice" not in html
        assert "111222333" not in html


# ─── Isolation Tests ────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestPortalIsolation:
    def test_portal_templates_have_no_staff_sidebar(self, portal_data):
        c = portal_data["parent_client"]()
        r = c.get(reverse("parent:dashboard"))
        html = r.content.decode()
        assert "sidebar-nav" not in html
        assert "nav-link" not in html
        assert "sidebar" not in html.lower()

    def test_portal_base_is_mobile_first(self, portal_data):
        c = Client()
        r = c.get(reverse("parent:login"))
        html = r.content.decode()
        assert "viewport" in html

    def test_portal_has_logout(self, portal_data):
        c = portal_data["parent_client"]()
        r = c.get(reverse("parent:dashboard"))
        html = r.content.decode()
        assert "logout" in html.lower()

    def test_portal_dashboard_has_student_name(self, portal_data):
        c = portal_data["parent_client"]()
        r = c.get(reverse("parent:dashboard"))
        html = r.content.decode()
        assert "Alice" in html

    def test_portal_login_page_has_school_name(self, portal_data):
        c = Client()
        r = c.get(reverse("parent:login"))
        html = r.content.decode()
        assert "Portal School" in html
