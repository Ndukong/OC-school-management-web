import re
from datetime import date, timedelta
from io import StringIO

import pytest
from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from core.models import License, School, UserProfile
from tests.factories import (
    PASSWORD,
    login_client,
    make_admin,
    make_school,
    make_school_with_license,
    make_student,
)


def _make_pending_license(school_name: str) -> License:
    return License.objects.create(
        product_key=f"OC-secfix-pending-{school_name.replace(' ', '-')[:24]}",
        school_name=school_name,
        max_students=100,
        expires_at=date.today() + timedelta(days=365),
        status="active",
    )


def _pin_session_license(client: Client, license_obj) -> None:
    session = client.session
    session["activate_license_id"] = license_obj.pk
    session.save()


def _login(username: str) -> Client:
    return login_client(username, PASSWORD)


@pytest.mark.django_db
class TestWizardStepHardening:
    def test_forged_step3_runs_school_step_instead(self):
        license_obj = _make_pending_license("Forge High")
        client = Client()
        _pin_session_license(client, license_obj)

        response = client.post(
            reverse("activate"),
            {
                "step": "3",
                "username": "hacker",
                "password": "hunter22",
                "password_confirm": "hunter22",
            },
            follow=True,
        )

        assert not User.objects.filter(username="hacker").exists()
        assert School.objects.filter(name_en="Forge High").exists()

        view_context_step = response.context["step"]
        assert view_context_step == 3

    def test_step3_rejected_when_admin_already_exists(self):
        school, license_obj = make_school_with_license("Done High", "SEC-DONE")
        make_admin("real-admin", school)
        client = Client()
        _pin_session_license(client, license_obj)

        response = client.post(
            reverse("activate"),
            {
                "step": "3",
                "username": "hacker",
                "password": "hunter22",
                "password_confirm": "hunter22",
            },
            follow=True,
        )

        assert not User.objects.filter(username="hacker").exists()
        messages = [str(m) for m in response.context["messages"]]
        assert any("already fully activated" in m for m in messages)
        assert "activate_license_id" not in client.session

    def test_step3_without_license_in_session_creates_nothing(self):
        client = Client()
        response = client.post(
            reverse("activate"),
            {
                "step": "3",
                "username": "hacker",
                "password": "hunter22",
                "password_confirm": "hunter22",
            },
            follow=True,
        )

        assert not User.objects.filter(username="hacker").exists()
        messages = [str(m) for m in response.context["messages"]]
        assert any("product key" in m.lower() for m in messages)

    def test_fully_activated_key_is_not_adopted_into_session(self):
        school, license_obj = make_school_with_license("Adopt High", "SEC-ADOPT")
        make_admin("adopt-admin", school)
        client = Client()

        response = client.post(
            reverse("activate"),
            {"step": "1", "product_key": license_obj.product_key},
            follow=True,
        )

        messages = [str(m) for m in response.context["messages"]]
        assert any("already been activated" in m for m in messages)
        assert "activate_license_id" not in client.session

    def test_mid_wizard_key_still_resumes(self):
        license_obj = _make_pending_license("Resume High")
        client = Client()

        response = client.post(
            reverse("activate"),
            {"step": "1", "product_key": license_obj.product_key},
            follow=True,
        )

        assert client.session.get("activate_license_id") == license_obj.pk
        assert response.context["step"] == 2


@pytest.mark.django_db
class TestSchoollessUserIdor:
    def test_student_detail_blocked_without_school_link(self):
        school = make_school("Iso High", "SEC-ID1")
        student = make_student(school, "SEC-ID1-001")
        User.objects.create_user(username="unlinked", password=PASSWORD)

        client = _login("unlinked")
        response = client.get(reverse("student_detail", args=[student.pk]))

        assert response.status_code == 302
        assert response.url == reverse("student_list")

    def test_student_edit_blocked_for_superuser_without_school(self):
        school = make_school("Iso High 2", "SEC-ID2")
        student = make_student(school, "SEC-ID2-001")
        User.objects.create_superuser(
            username="root", email="root@example.com", password=PASSWORD
        )

        client = _login("root")
        response = client.get(reverse("student_edit", args=[student.pk]))

        assert response.status_code == 302
        assert response.url == reverse("student_list")

    def test_student_edit_blocked_for_schoolless_admin_profile(self):
        school = make_school("Iso High 3", "SEC-ID3")
        student = make_student(school, "SEC-ID3-001")
        user = User.objects.create_user(username="schoolless", password=PASSWORD)
        UserProfile.objects.create(user=user, school=None, role="admin")

        client = _login("schoolless")
        response = client.get(reverse("student_edit", args=[student.pk]))

        assert response.status_code == 302
        assert response.url == reverse("student_list")

    def test_student_fee_status_blocked_without_school_link(self):
        school = make_school("Iso High 4", "SEC-ID4")
        student = make_student(school, "SEC-ID4-001")
        User.objects.create_superuser(
            username="root2", email="root2@example.com", password=PASSWORD
        )

        client = _login("root2")
        response = client.get(reverse("student_fee_status", args=[student.pk]))

        assert response.status_code == 302
        assert response.url == reverse("finance_dashboard")

    def test_linked_admin_still_sees_own_students(self):
        school = make_school("Iso High 5", "SEC-ID5")
        student = make_student(school, "SEC-ID5-001")
        make_admin("linked-admin", school)

        client = _login("linked-admin")
        response = client.get(reverse("student_detail", args=[student.pk]))

        assert response.status_code == 200
        assert student.full_name in response.content.decode()


@pytest.mark.django_db
class TestLicenseKeySigningParity:
    def test_web_generated_key_verifies_with_hmac(self):
        User.objects.create_superuser(
            username="key-root", email="key-root@example.com", password=PASSWORD
        )

        client = _login("key-root")
        response = client.post(
            reverse("generate_license_key"),
            {
                "school_name": "Web Key Academy",
                "max_students": 200,
                "max_devices": 2,
                "validity_days": 180,
            },
        )

        assert response.status_code == 200
        product_key = response.context["product_key"]
        payload = License.verify_product_key(product_key, settings.LICENSE_SECRET_KEY)
        assert payload is not None
        assert payload["school"] == "Web Key Academy"
        assert payload["max_students"] == 200

        lic = License(
            product_key=product_key,
            school_name="Web Key Academy",
            expires_at=date.today() + timedelta(days=180),
        )
        assert lic.validate_key(settings.LICENSE_SECRET_KEY)

    def test_web_generated_key_activates_through_wizard(self):
        User.objects.create_superuser(
            username="root3", email="root3@example.com", password=PASSWORD
        )
        client = _login("root3")
        response = client.post(
            reverse("generate_license_key"),
            {
                "school_name": "Wizard Key Academy",
                "max_students": 100,
                "max_devices": 3,
                "validity_days": 365,
            },
        )
        product_key = response.context["product_key"]

        client.logout()
        wizard = Client()
        wizard.post(reverse("activate"), {"step": "1", "product_key": product_key})

        assert License.objects.filter(
            school_name="Wizard Key Academy", school__isnull=True
        ).exists()

    def test_generate_license_command_output_verifies(self):
        out = StringIO()
        call_command(
            "generate_license",
            "Command Academy",
            "--max-students",
            "150",
            "--days",
            "90",
            stdout=out,
        )

        match = re.search(r"OC-[0-9a-f]{16}-[A-Za-z0-9_-]+", out.getvalue())
        assert match, out.getvalue()
        payload = License.verify_product_key(
            match.group(0), settings.LICENSE_SECRET_KEY
        )
        assert payload is not None
        assert payload["school"] == "Command Academy"
        assert payload["max_students"] == 150

    def test_tampered_key_is_rejected(self):
        product_key = License.generate_product_key(
            school_name="Tamper Me",
            max_students=100,
            max_devices=3,
            expires=date.today() + timedelta(days=30),
        )
        tampered = (
            product_key[:16]
            + ("0" if product_key[16] != "0" else "1")
            + product_key[17:]
        )

        assert License.verify_product_key(tampered, settings.LICENSE_SECRET_KEY) is None
