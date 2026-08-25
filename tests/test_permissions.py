import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from core.models import (
    AcademicTerm,
    School,
    SchoolClass,
    Subject,
    Teacher,
    TeacherAssignment,
    UserProfile,
)


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
    subject = Subject.objects.create(school=school, name="Math", code="MAT")
    term = AcademicTerm.objects.create(
        school=school, term_number=1, year_start=2025, year_end=2026, is_current=True
    )
    return {
        "school": school,
        "school_class": school_class,
        "subject": subject,
        "term": term,
    }


def make_user(username, school, role, password="pass"):
    user = User.objects.create_user(username=username, password=password)
    UserProfile.objects.create(user=user, school=school, role=role)
    return user


@pytest.mark.django_db
class TestRoleRequired:
    def test_unauthenticated_redirects_to_login(self):
        response = Client().get(reverse("compute_results"))
        assert response.status_code == 302
        assert "/login/" in response["Location"]

    def test_admin_allowed(self, school_data):
        make_user("admin", school_data["school"], "admin")
        c = Client()
        c.login(username="admin", password="pass")
        assert c.get(reverse("compute_results")).status_code == 200

    def test_teacher_forbidden(self, school_data):
        make_user("teacher1", school_data["school"], "teacher")
        c = Client()
        c.login(username="teacher1", password="pass")
        assert c.get(reverse("compute_results")).status_code == 403

    def test_bursar_forbidden(self, school_data):
        make_user("bursar1", school_data["school"], "bursar")
        c = Client()
        c.login(username="bursar1", password="pass")
        assert c.get(reverse("compute_results")).status_code == 403

    def test_staff_without_profile_forbidden(self, school_data):
        User.objects.create_user(username="plain", password="pass", is_staff=True)
        c = Client()
        c.login(username="plain", password="pass")
        assert c.get(reverse("compute_results")).status_code == 403

    def test_superuser_allowed_without_profile(self, school_data):
        User.objects.create_user(username="root", password="pass", is_superuser=True)
        c = Client()
        c.login(username="root", password="pass")
        assert c.get(reverse("compute_results")).status_code == 200


@pytest.mark.django_db
class TestAssignmentRequired:
    def test_assigned_teacher_can_open_mark_entry(self, school_data):
        data = school_data
        teacher = Teacher.objects.create(
            school=data["school"],
            first_name="Jane",
            last_name="Doe",
            teacher_code="T001",
        )
        TeacherAssignment.objects.create(
            teacher=teacher, school_class=data["school_class"], subject=data["subject"]
        )
        make_user("T001", data["school"], "teacher")
        c = Client()
        c.login(username="T001", password="pass")

        response = c.get(
            reverse("mark_entry", args=[data["school_class"].id, data["subject"].id])
        )

        assert response.status_code == 200

    def test_unassigned_teacher_redirected(self, school_data):
        data = school_data
        Teacher.objects.create(
            school=data["school"],
            first_name="Jane",
            last_name="Doe",
            teacher_code="T001",
        )
        make_user("T001", data["school"], "teacher")
        c = Client()
        c.login(username="T001", password="pass")

        response = c.get(
            reverse("mark_entry", args=[data["school_class"].id, data["subject"].id])
        )

        assert response.status_code == 302
        assert response["Location"].endswith("/teacher/")

    def test_non_teacher_redirected(self, school_data):
        data = school_data
        make_user("staff", data["school"], "teacher")
        c = Client()
        c.login(username="staff", password="pass")

        response = c.get(
            reverse("mark_entry", args=[data["school_class"].id, data["subject"].id])
        )

        assert response.status_code == 302


@pytest.mark.django_db
class TestAPIPermissions:
    def test_api_save_scores_requires_auth(self, school_data):
        data = school_data
        response = Client().post(
            reverse(
                "api_save_scores", args=[data["school_class"].id, data["subject"].id]
            ),
            data=[],
            content_type="application/json",
        )
        assert response.status_code in (401, 403)

    def test_api_save_scores_forbidden_for_unassigned_teacher(self, school_data):
        data = school_data
        Teacher.objects.create(
            school=data["school"],
            first_name="Jane",
            last_name="Doe",
            teacher_code="T002",
        )
        make_user("T002", data["school"], "teacher")
        c = Client()
        c.login(username="T002", password="pass")

        response = c.post(
            reverse(
                "api_save_scores", args=[data["school_class"].id, data["subject"].id]
            ),
            data=[],
            content_type="application/json",
        )

        assert response.status_code == 403

    def test_api_save_scores_allowed_for_assigned_teacher(self, school_data):
        data = school_data
        teacher = Teacher.objects.create(
            school=data["school"],
            first_name="Jane",
            last_name="Doe",
            teacher_code="T003",
        )
        TeacherAssignment.objects.create(
            teacher=teacher, school_class=data["school_class"], subject=data["subject"]
        )
        make_user("T003", data["school"], "teacher")
        c = Client()
        c.login(username="T003", password="pass")

        response = c.post(
            reverse(
                "api_save_scores", args=[data["school_class"].id, data["subject"].id]
            ),
            data=[],
            content_type="application/json",
        )

        assert response.status_code != 403

    def test_api_save_scores_allowed_for_admin(self, school_data):
        data = school_data
        make_user("admin", data["school"], "admin")
        c = Client()
        c.login(username="admin", password="pass")

        response = c.post(
            reverse(
                "api_save_scores", args=[data["school_class"].id, data["subject"].id]
            ),
            data=[],
            content_type="application/json",
        )

        assert response.status_code != 403

    def test_api_class_subject_forbidden_for_unassigned_teacher(self, school_data):
        data = school_data
        Teacher.objects.create(
            school=data["school"],
            first_name="Jane",
            last_name="Doe",
            teacher_code="T004",
        )
        make_user("T004", data["school"], "teacher")
        c = Client()
        c.login(username="T004", password="pass")

        response = c.get(
            reverse(
                "api_class_subject", args=[data["school_class"].id, data["subject"].id]
            )
        )

        assert response.status_code == 403

    def test_api_assignments_forbidden_for_non_teacher(self, school_data):
        make_user("plain", school_data["school"], "bursar")
        c = Client()
        c.login(username="plain", password="pass")

        response = c.get(reverse("api_assignments"))

        assert response.status_code == 403
