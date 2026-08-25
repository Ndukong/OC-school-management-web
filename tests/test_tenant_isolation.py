import base64
import hashlib
import hmac
import json
from datetime import date, timedelta
from types import SimpleNamespace

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from core.models import (
    AcademicTerm,
    License,
    School,
    SchoolClass,
    SMSConfig,
    SMSMessage,
    Student,
    UserProfile,
)

PASSWORD = "isolation-pass"


def _make_product_key(school_name: str, max_students: int = 500) -> str:
    payload = {
        "school": school_name,
        "max_students": max_students,
        "max_devices": 3,
        "expires": str(date.today() + timedelta(days=365)),
    }
    raw = (
        base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True).encode())
        .rstrip(b"=")
        .decode()
    )
    sig = hmac.new(
        settings.LICENSE_SECRET_KEY.encode(),
        json.dumps(payload, sort_keys=True).encode(),
        hashlib.sha256,
    ).hexdigest()[:16]
    return f"OC-{sig}-{raw}"


def _make_school(name: str, matricule: str):
    school = School.objects.create(
        name_en=name,
        matricule=matricule,
        region_en="North West",
        division_en="Mezam",
    )
    License.objects.create(
        product_key=f"OC-isotest-{matricule}",
        school=school,
        school_name=name,
        max_students=500,
        expires_at=date.today() + timedelta(days=365),
        status="active",
    )
    return school


def _make_admin(username: str, school) -> User:
    user = User.objects.create_user(username=username, password=PASSWORD)
    UserProfile.objects.create(user=user, school=school, role="admin")
    return user


def _login(username: str) -> Client:
    client = Client()
    assert client.login(username=username, password=PASSWORD)
    return client


@pytest.fixture
def two_schools():
    school_a = _make_school("Alpha High", "ISO-A")
    school_b = _make_school("Beta High", "ISO-B")

    admin_a = _make_admin("iso_admin_a", school_a)
    admin_b = _make_admin("iso_admin_b", school_b)

    def make_class(school, code):
        return SchoolClass.objects.create(
            school=school, name=f"Form 1 {code}", code=code, form_level=1
        )

    def make_term(school):
        return AcademicTerm.objects.create(
            school=school,
            term_number=1,
            year_start=2025,
            year_end=2026,
            is_current=True,
        )

    def make_student(school, unique_id):
        return Student.objects.create(
            school=school,
            first_name="Testy",
            sex="M",
            unique_id=unique_id,
            date_of_birth=date(2010, 5, 5),
            place_of_birth="Bamenda",
            guardian_name="Guardian",
            guardian_contact="600000000",
            division_of_origin="Mezam",
            region_of_origin="North West",
        )

    return SimpleNamespace(
        school_a=school_a,
        school_b=school_b,
        admin_a=admin_a.username,
        admin_b=admin_b.username,
        class_a=make_class(school_a, "FA1"),
        class_b=make_class(school_b, "FB1"),
        term_a=make_term(school_a),
        term_b=make_term(school_b),
        student_a=make_student(school_a, "ISO-A-001"),
        student_b=make_student(school_b, "ISO-B-001"),
    )


@pytest.mark.django_db
class TestCrossTenantIsolation:
    def test_same_tenant_access_still_works(self, two_schools):
        """Positive control: a school admin still sees their own objects."""
        client = _login(two_schools.admin_b)
        resp = client.get(
            reverse("student_detail", args=[two_schools.student_b.pk])
        )
        assert resp.status_code == 200

    def test_student_detail_cross_tenant_blocked(self, two_schools):
        client = _login(two_schools.admin_b)
        resp = client.get(
            reverse("student_detail", args=[two_schools.student_a.pk])
        )
        assert resp.status_code == 302

    def test_term_report_cross_tenant_404(self, two_schools):
        client = _login(two_schools.admin_b)
        url = reverse(
            "download_term_report",
            args=[two_schools.student_a.pk, two_schools.term_a.pk],
        )
        assert client.get(url).status_code == 404

    def test_preview_annual_report_cross_tenant_404(self, two_schools):
        client = _login(two_schools.admin_b)
        url = reverse(
            "preview_annual_report", args=[two_schools.student_a.pk, 2025, 2026]
        )
        assert client.get(url).status_code == 404

    def test_batch_report_cards_cross_tenant_404(self, two_schools):
        client = _login(two_schools.admin_b)
        url = reverse(
            "batch_report_cards",
            args=[two_schools.class_a.pk, two_schools.term_a.pk],
        )
        assert client.get(url).status_code == 404

    def test_export_marks_excel_cross_tenant_404(self, two_schools):
        client = _login(two_schools.admin_b)
        url = reverse(
            "export_marks_excel",
            args=[two_schools.class_a.pk, two_schools.term_a.pk],
        )
        assert client.get(url).status_code == 404

    def test_export_results_excel_cross_tenant_404(self, two_schools):
        client = _login(two_schools.admin_b)
        url = reverse("export_results_excel", args=[two_schools.term_a.pk])
        assert client.get(url).status_code == 404

    def test_compute_results_scoped_to_tenant(self, two_schools):
        client = _login(two_schools.admin_b)
        url = reverse("compute_results")
        # Cross-school ids must 404...
        resp = client.post(
            url,
            {
                "class_id": two_schools.class_a.pk,
                "term_id": two_schools.term_a.pk,
            },
        )
        assert resp.status_code == 404
        # ...and own-school ids must work.
        resp_own = client.post(
            url,
            {
                "class_id": two_schools.class_b.pk,
                "term_id": two_schools.term_b.pk,
            },
        )
        assert resp_own.status_code == 200

    def test_sms_cancel_cross_tenant_404(self, two_schools):
        config = SMSConfig.objects.create(
            school=two_schools.school_a, provider="manual", is_active=True
        )
        sms = SMSMessage.objects.create(
            config=config,
            recipient_number="+237600000001",
            message="hi",
            status="queued",
        )
        client = _login(two_schools.admin_b)
        url = reverse("sms_cancel", args=[sms.pk])
        assert client.get(url).status_code == 404

    def test_generate_license_key_forbidden_for_school_admin(self, two_schools):
        client = _login(two_schools.admin_b)
        url = reverse("generate_license_key")
        resp = client.post(
            url,
            {"school_name": "Sneaky School", "validity_days": 365},
        )
        assert resp.status_code == 403

    def test_backup_download_forbidden_for_school_admin(self, two_schools):
        client = _login(two_schools.admin_b)
        url = reverse("download_backup", args=[1])
        assert client.get(url).status_code == 403

    def test_backup_management_forbidden_for_school_admin(self, two_schools):
        client = _login(two_schools.admin_b)
        assert client.get(reverse("backup_management")).status_code == 403

    def test_django_admin_blocked_for_school_admin(self, two_schools):
        client = _login(two_schools.admin_b)
        assert client.get("/admin/").status_code == 403

    def test_django_admin_allows_real_superuser(self, two_schools):
        User.objects.create_user(
            username="platform_owner",
            password=PASSWORD,
            is_staff=True,
            is_superuser=True,
        )
        client = _login("platform_owner")
        resp = client.get("/admin/")
        assert resp.status_code in (200, 302)


@pytest.mark.django_db
class TestActivationWizardMultiTenant:
    def test_activation_creates_scoped_non_superuser_admin(self):
        key = _make_product_key("Wizard High")
        client = Client()

        resp = client.post(reverse("activate"), {"step": "1", "product_key": key})
        assert resp.status_code == 302

        resp = client.post(
            reverse("activate"),
            {
                "step": "2",
                "name_en": "Wizard High",
                "region_en": "Littoral",
                "division_en": "Wouri",
                "phone": "233456789",
                "motto_en": "Learn",
            },
        )
        assert resp.status_code == 302

        resp = client.post(
            reverse("activate"),
            {
                "step": "3",
                "username": "wizard_admin",
                "password": "secret123",
                "password_confirm": "secret123",
                "first_name": "Wizard",
                "last_name": "Admin",
                "email": "wizard@example.com",
            },
        )
        assert resp.status_code == 302

        user = User.objects.get(username="wizard_admin")
        assert user.is_superuser is False
        assert user.is_staff is False
        profile = user.profile
        assert profile.role == "admin"
        assert profile.school is not None
        assert profile.school.name_en == "Wizard High"
        license_obj = License.objects.get(product_key=key)
        assert license_obj.school_id == profile.school.pk
        assert profile.school.subjects.count() > 0

    def test_second_school_can_activate_independently(self):
        first = _make_product_key("First School")
        second = _make_product_key("Second School")
        client = Client()
        for key, username in ((first, "first_admin"), (second, "second_admin")):
            client.post(reverse("activate"), {"step": "1", "product_key": key})
            client.post(
                reverse("activate"),
                {"step": "2", "name_en": f"{username} school"},
            )
            client.post(
                reverse("activate"),
                {
                    "step": "3",
                    "username": username,
                    "password": "secret123",
                    "password_confirm": "secret123",
                },
            )
        u1 = User.objects.get(username="first_admin")
        u2 = User.objects.get(username="second_admin")
        assert u1.profile.school_id != u2.profile.school_id


@pytest.mark.django_db
class TestDataTransfer:
    def test_export_then_import_round_trip(self, two_schools):
        import json as _json

        from core.utils.school_export import build_school_export, restore_school_export

        payload = build_school_export(two_schools.school_a)
        assert payload["schema"] == "oc-school-export"
        assert any(s["unique_id"] == "ISO-A-001" for s in payload["students"])
        assert not any(
            s["unique_id"] == "ISO-B-001" for s in payload["students"]
        )

        # Importing into another school must keep catalog data but refuse
        # students whose globally-unique IDs belong elsewhere.
        counts = restore_school_export(payload, two_schools.school_b)
        assert counts["student_conflicts"] == 1
        # Identical natural-key term already exists at B -> nothing "new".
        assert two_schools.school_b.terms.filter(
            year_start=2025, year_end=2026
        ).exists()
        assert counts["classes"] >= 1

        # Re-keyed IDs import cleanly (true migration scenario).
        payload2 = _json.loads(_json.dumps(payload))
        for s in payload2["students"]:
            s["unique_id"] = "J" + s["unique_id"][1:]
        for e in payload2["enrollments"]:
            e["student"] = "J" + e["student"][1:]
        counts2 = restore_school_export(payload2, two_schools.school_b)
        assert counts2["students"] >= 1
        assert counts2["student_conflicts"] == 0
        assert two_schools.school_b.students.filter(
            unique_id="JSO-A-001"
        ).exists()

    def test_export_view_scoped_and_downloadable(self, two_schools):
        client = _login(two_schools.admin_b)
        resp = client.get(reverse("school_data_export"))
        assert resp.status_code == 200
        assert "attachment" in resp["Content-Disposition"]
        body = resp.content.decode()
        assert "ISO-B-001" in body
        assert "ISO-A-001" not in body

    def test_data_transfer_page_renders_for_admin(self, two_schools):
        client = _login(two_schools.admin_b)
        assert client.get(reverse("school_data_transfer")).status_code == 200


@pytest.mark.django_db
class TestStudentQuotaEnforcement:
    def test_student_create_blocked_at_license_limit(self):
        school = _make_school("Tiny School", "ISO-Q")
        License.objects.update(school=school, max_students=1)
        Student.objects.create(
            school=school,
            first_name="Full",
            sex="M",
            unique_id="Q-001",
            date_of_birth=date(2010, 1, 1),
        )
        _make_admin("quota_admin", school)
        client = _login("quota_admin")

        before = Student.objects.filter(school=school).count()
        resp = client.post(reverse("student_create"), {"first_name": "Extra"})
        assert resp.status_code == 302
        assert Student.objects.filter(school=school).count() == before
