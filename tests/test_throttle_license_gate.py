import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from tests.factories import (
    PASSWORD,
    login_client,
    make_admin,
    make_school,
    make_school_with_license,
    make_student,
)


def _login(username: str) -> Client:
    return login_client(username, PASSWORD)


@pytest.mark.django_db
class TestStaffLoginThrottle:
    def test_lockout_survives_new_session(self):
        User.objects.create_user(username="tl1", password=PASSWORD)
        first = Client()
        for _ in range(5):
            first.post(reverse("login"), {"username": "tl1", "password": "wrong"})

        fresh = Client()
        response = fresh.post(
            reverse("login"), {"username": "tl1", "password": PASSWORD}
        )
        assert b"Too many failed attempts" in response.content

    def test_ip_lockout_blocks_any_username(self):
        for i in range(20):
            Client().post(
                reverse("login"), {"username": f"ipu{i}", "password": "wrong"}
            )
        response = Client().post(
            reverse("login"), {"username": "innocent", "password": "x"}
        )
        assert b"Too many failed attempts" in response.content

    def test_successful_login_resets_counter(self):
        User.objects.create_user(username="tl3", password=PASSWORD)
        first = Client()
        for _ in range(4):
            first.post(reverse("login"), {"username": "tl3", "password": "wrong"})
        response = first.post(
            reverse("login"), {"username": "tl3", "password": PASSWORD}
        )
        assert response.status_code == 302

        fresh = Client()
        for _ in range(4):
            fresh.post(reverse("login"), {"username": "tl3", "password": "wrong"})
        response = fresh.post(
            reverse("login"), {"username": "tl3", "password": PASSWORD}
        )
        assert response.status_code == 302

    def test_below_limit_still_allows_login(self):
        User.objects.create_user(username="tl4", password=PASSWORD)
        client = Client()
        for _ in range(4):
            client.post(reverse("login"), {"username": "tl4", "password": "wrong"})
        response = client.post(
            reverse("login"), {"username": "tl4", "password": PASSWORD}
        )
        assert response.status_code == 302


@pytest.mark.django_db
class TestParentPortalThrottle:
    def test_parent_lockout_survives_new_session(self):
        school = make_school("PT High", "PT-1")
        make_student(school, "P777777777", guardian_contact="677000111")
        first = Client()
        for _ in range(5):
            first.post(
                reverse("parent:login"),
                {"unique_id": "P777777777", "guardian_contact": "wrong"},
            )

        fresh = Client()
        response = fresh.post(
            reverse("parent:login"),
            {"unique_id": "P777777777", "guardian_contact": "677000111"},
        )
        assert b"Too many failed attempts" in response.content
        assert fresh.session.get("parent_student_id") is None

    def test_parent_session_key_cycles_on_login(self):
        school = make_school("PT High 2", "PT-2")
        make_student(school, "P888888888", guardian_contact="677222333")
        client = Client()
        client.get(reverse("parent:login"))
        session = client.session
        session["probe"] = 1
        session.save()
        key_before = session.session_key

        response = client.post(
            reverse("parent:login"),
            {"unique_id": "P888888888", "guardian_contact": "677222333"},
        )

        assert response.status_code == 302
        assert client.session.session_key != key_before
        assert client.session.get("parent_student_id") is not None


@pytest.mark.django_db
class TestLicenseGate:
    def test_lapsed_license_blocks_deep_urls(self):
        school, license_obj = make_school_with_license("Gate High", "GATE-1")
        make_admin("gate_admin", school)
        client = Client()
        assert client.login(username="gate_admin", password=PASSWORD)

        response = client.get(reverse("student_list"))
        assert response.status_code == 200

        license_obj.status = "expired"
        license_obj.save()

        for url_name in ("student_list", "reports_hub", "finance_dashboard"):
            response = client.get(reverse(url_name))
            assert response.status_code == 302, url_name
            assert response.url == reverse("activate"), url_name

    def test_activation_page_reachable_when_lapsed(self):
        school, license_obj = make_school_with_license("Gate High 3", "GATE-3")
        make_admin("gate_admin3", school)
        client = Client()
        assert client.login(username="gate_admin3", password=PASSWORD)

        license_obj.status = "revoked"
        license_obj.save()

        response = client.get(reverse("activate"))
        assert response.status_code == 200
        response = client.get(reverse("login"))
        assert response.status_code == 302

    def test_superuser_exempt_from_gate(self):
        _school, license_obj = make_school_with_license("Gate High 4", "GATE-4")
        license_obj.status = "expired"
        license_obj.save()
        User.objects.create_superuser(
            username="groot", email="g@example.com", password=PASSWORD
        )
        client = Client()
        assert client.login(username="groot", password=PASSWORD)

        response = client.get(reverse("student_list"))
        assert response.status_code == 200

    def test_school_without_license_not_gated(self):
        school = make_school("NoLic High", "NL-1")
        make_admin("nolic_admin", school)
        client = Client()
        assert client.login(username="nolic_admin", password=PASSWORD)

        response = client.get(reverse("student_list"))
        assert response.status_code == 200

    def test_parent_portal_blocked_when_license_lapsed(self):
        school, license_obj = make_school_with_license("Gate High 5", "GATE-5")
        student = make_student(school, "P555555555", guardian_contact="677111222")
        license_obj.status = "expired"
        license_obj.save()
        client = Client()

        response = client.post(
            reverse("parent:login"),
            {"unique_id": "P555555555", "guardian_contact": "677111222"},
            follow=True,
        )
        messages = [str(m) for m in response.context["messages"]]
        assert any("license has expired" in m for m in messages)
        assert client.session.get("parent_student_id") is None

        session = client.session
        session["parent_student_id"] = student.pk
        session.save()
        response = client.get(reverse("parent:dashboard"), follow=True)
        assert response.redirect_chain[-1][0] == reverse("parent:login")
        assert client.session.get("parent_student_id") is None
        messages = [str(m) for m in response.context["messages"]]
        assert any("license has expired" in m for m in messages)
