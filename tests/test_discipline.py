from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from core.models import (
    AcademicTerm,
    AttendanceRecord,
    AttendanceRegister,
    ConductThreshold,
    DisciplineSummary,
    Punishment,
    School,
    SchoolClass,
    Student,
    StudentEnrollment,
    Subject,
    Teacher,
    TeacherAssignment,
    UserProfile,
)
from core.utils.discipline import compute_discipline_summaries


@pytest.fixture
def data():
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
    subject = Subject.objects.create(school=school, name="Math", code="MAT")
    student = Student.objects.create(
        school=school,
        first_name="John",
        other_names="X",
        sex="M",
        unique_id="STU001",
        date_of_birth=date(2010, 1, 1),
        place_of_birth="Buea",
        guardian_name="Guardian",
        division_of_origin="Fako",
        region_of_origin="South West",
    )
    StudentEnrollment.objects.create(
        student=student, school_class=school_class, academic_term=term
    )
    return {
        "school": school,
        "school_class": school_class,
        "term": term,
        "student": student,
        "subject": subject,
    }


def make_user(username, school, role, password="pass"):
    user = User.objects.create_user(username=username, password=password)
    UserProfile.objects.create(user=user, school=school, role=role)
    return user


def make_teacher(data, code, is_class_master=False):
    teacher = Teacher.objects.create(
        school=data["school"],
        first_name="Jane",
        last_name="Doe",
        teacher_code=code,
    )
    TeacherAssignment.objects.create(
        teacher=teacher,
        school_class=data["school_class"],
        subject=data["subject"],
        is_class_master=is_class_master,
    )
    return teacher


@pytest.mark.django_db
class TestAttendanceEntry:
    def test_save_creates_register_and_records(self, data):
        make_user("admin", data["school"], "admin")
        c = Client()
        c.login(username="admin", password="pass")

        response = c.post(
            reverse("attendance_entry"),
            {
                "action": "save",
                "class_id": data["school_class"].id,
                "date": "2026-03-10",
                f"status_{data['student'].id}_1": "A",
                f"status_{data['student'].id}_2": "P",
            },
        )

        assert response.status_code == 302
        register = AttendanceRegister.objects.get(
            school_class=data["school_class"],
            date=date(2026, 3, 10),
            period=1,
        )
        record = AttendanceRecord.objects.get(
            register=register, student=data["student"]
        )
        assert record.status == "A"

    def test_plain_teacher_denied(self, data):
        make_teacher(data, "T001", is_class_master=False)
        make_user("T001", data["school"], "teacher")
        c = Client()
        c.login(username="T001", password="pass")

        response = c.get(
            reverse("attendance_entry"),
            {"class_id": data["school_class"].id, "date": "2026-03-10"},
        )

        assert response.status_code == 302

    def test_class_master_allowed(self, data):
        make_teacher(data, "T002", is_class_master=True)
        make_user("T002", data["school"], "teacher")
        c = Client()
        c.login(username="T002", password="pass")

        response = c.get(
            reverse("attendance_entry"),
            {"class_id": data["school_class"].id, "date": "2026-03-10"},
        )

        assert response.status_code == 200


@pytest.mark.django_db
class TestDisciplineSummary:
    def test_compute_aggregates_attendance_and_punishments(self, data):
        register = AttendanceRegister.objects.create(
            school_class=data["school_class"], date=date(2026, 3, 10), period=1
        )
        AttendanceRecord.objects.create(
            register=register, student=data["student"], status="A"
        )
        register2 = AttendanceRegister.objects.create(
            school_class=data["school_class"], date=date(2026, 3, 10), period=2
        )
        AttendanceRecord.objects.create(
            register=register2, student=data["student"], status="A"
        )
        register3 = AttendanceRegister.objects.create(
            school_class=data["school_class"], date=date(2026, 3, 11), period=1
        )
        AttendanceRecord.objects.create(
            register=register3, student=data["student"], status="PRM"
        )
        register4 = AttendanceRegister.objects.create(
            school_class=data["school_class"], date=date(2026, 3, 12), period=1
        )
        AttendanceRecord.objects.create(
            register=register4, student=data["student"], status="L"
        )
        Punishment.objects.create(
            student=data["student"],
            academic_term=data["term"],
            hours=Decimal("2.5"),
            reason="Noise making",
            date_given=date(2026, 3, 13),
        )

        result = compute_discipline_summaries(data["school_class"], data["term"])

        summary = result["rows"][0]["summary"]
        assert summary.unjustified_abs_hours == Decimal("2.0")
        assert summary.justified_abs_hours == Decimal("1.0")
        assert summary.lateness_count == 1
        assert summary.punishment_hours == Decimal("2.5")
        assert summary.conduct_decision == ""

    def test_conduct_decision_from_thresholds(self, data):
        ConductThreshold.objects.create(
            school=data["school"],
            conduct_type="warning",
            min_unjustified_abs=2,
        )
        ConductThreshold.objects.create(
            school=data["school"],
            conduct_type="reprimand",
            min_unjustified_abs=4,
        )
        register = AttendanceRegister.objects.create(
            school_class=data["school_class"], date=date(2026, 3, 10), period=1
        )
        AttendanceRecord.objects.create(
            register=register, student=data["student"], status="A"
        )

        result = compute_discipline_summaries(data["school_class"], data["term"])

        assert result["rows"][0]["summary"].conduct_decision == ""
        assert result["rows"][0]["summary"].unjustified_abs_hours == Decimal("1.0")

        register2 = AttendanceRegister.objects.create(
            school_class=data["school_class"], date=date(2026, 3, 11), period=1
        )
        AttendanceRecord.objects.create(
            register=register2, student=data["student"], status="A"
        )

        result = compute_discipline_summaries(data["school_class"], data["term"])
        assert result["rows"][0]["summary"].conduct_decision == "warning"

    def test_summary_view_class_master_allowed(self, data):
        make_teacher(data, "T003", is_class_master=True)
        make_user("T003", data["school"], "teacher")
        c = Client()
        c.login(username="T003", password="pass")

        response = c.get(
            reverse("discipline_summary"),
            {"class_id": data["school_class"].id, "term_id": data["term"].id},
        )

        assert response.status_code == 200
        assert DisciplineSummary.objects.count() == 1

    def test_summary_view_plain_teacher_denied(self, data):
        make_teacher(data, "T004", is_class_master=False)
        make_user("T004", data["school"], "teacher")
        c = Client()
        c.login(username="T004", password="pass")

        response = c.get(
            reverse("discipline_summary"),
            {"class_id": data["school_class"].id, "term_id": data["term"].id},
        )

        assert response.status_code == 302
        assert DisciplineSummary.objects.count() == 0
