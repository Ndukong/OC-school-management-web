import json
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from core.models import (
    AcademicTerm,
    ClassSubject,
    Competency,
    CompetencyScore,
    School,
    SchoolClass,
    Student,
    StudentEnrollment,
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
    ClassSubject.objects.create(school_class=school_class, subject=subject)
    term = AcademicTerm.objects.create(
        school=school,
        term_number=1,
        year_start=2025,
        year_end=2026,
        is_current=True,
    )
    comp = Competency.objects.create(
        subject=subject,
        term=term,
        form_level=1,
        description="Compute",
        sort_order=1,
    )
    student = Student.objects.create(
        school=school,
        first_name="A",
        other_names="B",
        sex="M",
        unique_id="100000001",
        date_of_birth=date(2010, 1, 1),
        place_of_birth="X",
        guardian_name="G",
        division_of_origin="D",
        region_of_origin="R",
    )
    StudentEnrollment.objects.create(
        student=student, school_class=school_class, academic_term=term
    )
    teacher = Teacher.objects.create(
        school=school, first_name="Jane", last_name="Doe", teacher_code="T001"
    )
    TeacherAssignment.objects.create(
        teacher=teacher, school_class=school_class, subject=subject
    )
    user = User.objects.create_user(username="T001", password="pass")
    UserProfile.objects.create(
        user=user, school=school, role="teacher", teacher=teacher
    )
    admin_user = User.objects.create_user(
        username="admin", password="pass", is_staff=True
    )
    UserProfile.objects.create(user=admin_user, school=school, role="admin")

    return {
        "school": school,
        "school_class": school_class,
        "subject": subject,
        "term": term,
        "comp": comp,
        "student": student,
        "teacher": teacher,
        "teacher_user": user,
        "admin_user": admin_user,
    }


# ------------------------------------------------------------------
# mark_entry_select
# ------------------------------------------------------------------
@pytest.mark.django_db
class TestMarkEntrySelect:
    def test_redirect_single_assignment(self, school_data):
        c = Client()
        c.login(username="T001", password="pass")
        resp = c.get(reverse("mark_entry_select"))
        assert resp.status_code == 302
        sd = school_data
        expected = reverse(
            "mark_entry_grid",
            args=[sd["school_class"].id, sd["subject"].id, sd["term"].id],
        )
        assert resp["Location"] == expected

    def test_auto_redirect_to_grid(self, school_data):
        c = Client()
        c.login(username="T001", password="pass")
        resp = c.get(reverse("mark_entry_select"))
        sd = school_data
        expected = reverse(
            "mark_entry_grid",
            args=[sd["school_class"].id, sd["subject"].id, sd["term"].id],
        )
        assert resp["Location"] == expected

    def test_admin_also_redirects_for_single_assignment(self, school_data):
        c = Client()
        c.login(username="admin", password="pass")
        resp = c.get(reverse("mark_entry_select"))
        assert resp.status_code == 302

    def test_requires_login(self):
        resp = Client().get(reverse("mark_entry_select"))
        assert resp.status_code == 302


# ------------------------------------------------------------------
# mark_entry (grid)
# ------------------------------------------------------------------
@pytest.mark.django_db
class TestMarkEntryGrid:
    def _get_grid_url(self, sd, term_id=None):
        if term_id:
            return reverse(
                "mark_entry_grid",
                args=[sd["school_class"].id, sd["subject"].id, term_id],
            )
        return reverse("mark_entry", args=[sd["school_class"].id, sd["subject"].id])

    def test_grid_renders_for_assigned_teacher(self, school_data):
        c = Client()
        c.login(username="T001", password="pass")
        resp = c.get(self._get_grid_url(school_data))
        assert resp.status_code == 200
        assert b"Math" in resp.content

    def test_grid_with_term_id(self, school_data):
        c = Client()
        c.login(username="T001", password="pass")
        resp = c.get(self._get_grid_url(school_data, school_data["term"].id))
        assert resp.status_code == 200

    def test_fallback_post_saves_scores(self, school_data):
        c = Client()
        c.login(username="T001", password="pass")
        sd = school_data
        resp = c.post(
            self._get_grid_url(sd),
            {f"score_{sd['student'].id}_{sd['comp'].id}": "14.75"},
        )
        assert resp.status_code == 302
        score = CompetencyScore.objects.get(
            student=sd["student"],
            competency=sd["comp"],
            academic_term=sd["term"],
        )
        assert score.score == Decimal("14.75")

    def test_compute_requires_admin(self, school_data):
        c = Client()
        c.login(username="T001", password="pass")
        sd = school_data
        # Teacher's compute POST falls to the else branch (fallback save + redirect)
        resp = c.post(
            self._get_grid_url(sd),
            {"action": "compute"},
        )
        assert resp.status_code == 302
        assert CompetencyScore.objects.count() == 0

    def test_compute_allows_admin(self, school_data):
        c = Client()
        c.login(username="admin", password="pass")
        resp = c.post(
            self._get_grid_url(school_data),
            {"action": "compute"},
        )
        assert resp.status_code == 200
        assert b"Results" in resp.content

    def test_unassigned_teacher_forbidden(self, school_data):
        sd = school_data
        t = Teacher.objects.create(
            school=sd["school"],
            first_name="Un",
            last_name="Known",
            teacher_code="T999",
        )
        u = User.objects.create_user(username="T999", password="pass")
        UserProfile.objects.create(
            user=u, school=sd["school"], role="teacher", teacher=t
        )
        c = Client()
        c.login(username="T999", password="pass")
        resp = c.get(self._get_grid_url(sd))
        assert resp.status_code == 302


# ------------------------------------------------------------------
# save_score_cell (HTMX endpoint)
# ------------------------------------------------------------------
@pytest.mark.django_db
class TestSaveScoreCell:
    def _url(self, sd):
        return reverse("save_score_cell")

    def test_save_valid_score(self, school_data):
        c = Client()
        c.login(username="T001", password="pass")
        resp = c.post(
            self._url(school_data),
            {
                "student_id": school_data["student"].id,
                "competency_id": school_data["comp"].id,
                "term_id": school_data["term"].id,
                "score": "15.50",
            },
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data["saved"] is True
        assert data["student_id"] == school_data["student"].id
        assert float(data["average"]) == pytest.approx(15.50, abs=0.01)
        score = CompetencyScore.objects.get(
            student=school_data["student"],
            competency=school_data["comp"],
            academic_term=school_data["term"],
        )
        assert score.score == Decimal("15.50")

    def test_clear_score(self, school_data):
        sd = school_data
        CompetencyScore.objects.create(
            student=sd["student"],
            competency=sd["comp"],
            academic_term=sd["term"],
            score=Decimal("18.00"),
        )
        c = Client()
        c.login(username="T001", password="pass")
        resp = c.post(
            self._url(sd),
            {
                "student_id": sd["student"].id,
                "competency_id": sd["comp"].id,
                "term_id": sd["term"].id,
                "score": "",
            },
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data["saved"] is True
        assert not CompetencyScore.objects.filter(
            student=sd["student"], competency=sd["comp"]
        ).exists()

    def test_reject_out_of_range(self, school_data):
        c = Client()
        c.login(username="T001", password="pass")
        resp = c.post(
            self._url(school_data),
            {
                "student_id": school_data["student"].id,
                "competency_id": school_data["comp"].id,
                "term_id": school_data["term"].id,
                "score": "25",
            },
        )
        assert resp.status_code == 400
        data = json.loads(resp.content)
        assert "20" in data["error"]

    def test_reject_invalid_score(self, school_data):
        c = Client()
        c.login(username="T001", password="pass")
        resp = c.post(
            self._url(school_data),
            {
                "student_id": school_data["student"].id,
                "competency_id": school_data["comp"].id,
                "term_id": school_data["term"].id,
                "score": "abc",
            },
        )
        assert resp.status_code == 400

    def test_unassigned_teacher_rejected(self, school_data):
        sd = school_data
        t = Teacher.objects.create(
            school=sd["school"],
            first_name="Stranger",
            last_name="X",
            teacher_code="T998",
        )
        u = User.objects.create_user(username="T998", password="pass")
        UserProfile.objects.create(
            user=u, school=sd["school"], role="teacher", teacher=t
        )
        c = Client()
        c.login(username="T998", password="pass")
        resp = c.post(
            self._url(sd),
            {
                "student_id": sd["student"].id,
                "competency_id": sd["comp"].id,
                "term_id": sd["term"].id,
                "score": "10",
            },
        )
        assert resp.status_code == 403

    def test_admin_can_save(self, school_data):
        c = Client()
        c.login(username="admin", password="pass")
        resp = c.post(
            self._url(school_data),
            {
                "student_id": school_data["student"].id,
                "competency_id": school_data["comp"].id,
                "term_id": school_data["term"].id,
                "score": "12.50",
            },
        )
        assert resp.status_code == 200
        data = json.loads(resp.content)
        assert data["saved"] is True

    def test_get_not_allowed(self, school_data):
        c = Client()
        c.login(username="T001", password="pass")
        resp = c.get(self._url(school_data))
        assert resp.status_code == 405

    def test_requires_auth(self, school_data):
        resp = Client().post(
            self._url(school_data),
            {
                "student_id": school_data["student"].id,
                "competency_id": school_data["comp"].id,
                "term_id": school_data["term"].id,
                "score": "10",
            },
        )
        assert resp.status_code == 302


# ------------------------------------------------------------------
# UserProfile linked teacher helpers
# ------------------------------------------------------------------
@pytest.mark.django_db
class TestUserProfileTeacher:
    def test_assigned_classes(self, school_data):
        sd = school_data
        profile = sd["teacher_user"].profile
        qs = profile.assigned_classes
        assert qs.count() == 1
        assert qs.first().id == sd["school_class"].id

    def test_assigned_subjects(self, school_data):
        sd = school_data
        profile = sd["teacher_user"].profile
        qs = profile.assigned_subjects
        assert qs.count() == 1
        assert qs.first().id == sd["subject"].id

    def test_teacher_resolution_prefers_fk(self, school_data):
        from core.utils.permissions import get_teacher_for_user

        teacher = get_teacher_for_user(school_data["teacher_user"])
        assert teacher.id == school_data["teacher"].id

    def test_fallback_matching_without_fk(self, school_data):
        from core.utils.permissions import get_teacher_for_user

        user = User.objects.create_user(username="fallback", password="pass")
        Teacher.objects.create(
            school=school_data["school"],
            first_name="Unique",
            last_name="Teacher",
            teacher_code="FB002",
        )
        # User has no matching teacher by code, email, or name yet
        assert get_teacher_for_user(user) is None
        # After setting email to match teacher's email, fallback finds it
        teacher = Teacher.objects.get(teacher_code="FB002")
        teacher.email = "fallback@example.com"
        teacher.save()
        user.email = "fallback@example.com"
        user.save()
        t = get_teacher_for_user(user)
        assert t is not None
        assert t.pk == teacher.pk
