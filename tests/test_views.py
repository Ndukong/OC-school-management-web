from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from core.models import (
    AcademicTerm,
    Competency,
    CompetencyScore,
    School,
    SchoolClass,
    Student,
    StudentEnrollment,
    Subject,
    UserProfile,
)


@pytest.mark.django_db
class TestTeacherDashboard:
    def test_dashboard_requires_login(self):
        c = Client()
        response = c.get(reverse("teacher_dashboard"))
        assert response.status_code == 302

    def test_dashboard_authenticated_no_teacher(self):
        User.objects.create_user(username="test", password="pass")
        c = Client()
        c.login(username="test", password="pass")
        response = c.get(reverse("teacher_dashboard"))
        # Without a license, dashboard redirects to activate
        assert response.status_code in (200, 302)

    def test_mark_entry_requires_login(self):
        c = Client()
        response = c.get("/teacher/marks/1/1/")
        assert response.status_code == 302


@pytest.mark.django_db
class TestGradingAPI:
    def test_api_assignments_requires_auth(self):
        c = Client()
        response = c.get(reverse("api_assignments"))
        assert response.status_code in (401, 403)

    def test_mark_entry_view_not_found_for_invalid_ids(self):
        User.objects.create_user(username="admin", password="pass", is_staff=True)
        c = Client()
        c.login(username="admin", password="pass")
        response = c.get("/teacher/marks/999/999/")
        assert response.status_code in (302, 404)  # redirects if no school/profile


@pytest.mark.django_db
class TestMarkEntrySave:
    def test_scores_save_and_reload(self):
        school = School.objects.create(
            name_en="Test School", matricule="TEST001",
            region_en="South West", division_en="Fako",
        )
        school_class = SchoolClass.objects.create(
            school=school, name="Form 1", code="F1", form_level=1
        )
        term = AcademicTerm.objects.create(
            school=school, term_number=1, year_start=2025, year_end=2026, is_current=True
        )
        subject = Subject.objects.create(school=school, name="Math", code="MAT")
        comp = Competency.objects.create(
            subject=subject, term=term, form_level=1, description="Compute"
        )
        student = Student.objects.create(
            school=school, first_name="A", other_names="B", sex="M",
            unique_id="100000001", date_of_birth=date(2010, 1, 1),
            place_of_birth="X", guardian_name="G",
            division_of_origin="D", region_of_origin="R",
        )
        StudentEnrollment.objects.create(
            student=student, school_class=school_class, academic_term=term
        )
        user = User.objects.create_user(username="admin", password="pass", is_staff=True)
        UserProfile.objects.create(user=user, school=school, role="admin")
        c = Client()
        c.login(username="admin", password="pass")

        post = c.post(
            reverse("mark_entry", args=[school_class.id, subject.id]),
            {f"score_{student.id}_{comp.id}": "15.5"},
        )
        assert post.status_code == 302

        score = CompetencyScore.objects.get(
            student=student, competency=comp, academic_term=term
        )
        assert score.score == Decimal("15.50")

        reload = c.get(reverse("mark_entry", args=[school_class.id, subject.id]))
        assert 'value="15.50"' in reload.content.decode()
