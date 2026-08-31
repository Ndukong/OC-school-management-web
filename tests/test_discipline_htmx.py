import json
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from core.models import (
    AcademicTerm,
    AttendanceRecord,
    ConductThreshold,
    License,
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
def data():
    school = School.objects.create(
        name_en="S", matricule="SMK1", region_en="SW", division_en="F"
    )
    klass = SchoolClass.objects.create(
        school=school, name="F1", code="F1", form_level=1
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
        unique_id="S9",
        date_of_birth=date(2010, 1, 1),
        place_of_birth="B",
        guardian_name="G",
        division_of_origin="F",
        region_of_origin="SW",
    )
    StudentEnrollment.objects.create(
        student=student, school_class=klass, academic_term=term
    )
    user = User.objects.create_user(username="admin", password="pass")
    UserProfile.objects.create(user=user, school=school, role="admin")
    return {
        "school": school,
        "klass": klass,
        "term": term,
        "student": student,
        "user": user,
        "subject": subject,
    }


@pytest.mark.django_db
class TestNewFeatures:
    def test_attendance_page_and_cell_save(self, data):
        c = Client()
        c.login(username="admin", password="pass")

        r = c.get(
            reverse("attendance_entry"),
            {"class_id": data["klass"].id, "date": "2026-03-10"},
        )
        assert r.status_code == 200
        body = r.content.decode()
        assert reverse("save_attendance_cell") in body
        assert "summary-bar" in body
        assert "P8" in body  # default 8 periods per day

        r = c.post(
            reverse("save_attendance_cell"),
            {
                "class_id": data["klass"].id,
                "date": "2026-03-10",
                "period": 1,
                "student_id": data["student"].id,
                "status": "",
            },
        )
        assert r.status_code == 200
        payload = json.loads(r.content)
        assert payload["saved"] is True
        assert payload["status"] == "P"
        assert payload["summary"]["total"] == 1
        assert payload["summary"]["present"] == 1
        assert (
            AttendanceRecord.objects.get(
                register__school_class=data["klass"],
                register__date=date(2026, 3, 10),
                register__period=1,
                student=data["student"],
            ).status
            == "P"
        )

        r = c.post(
            reverse("save_attendance_cell"),
            {
                "class_id": data["klass"].id,
                "date": "2026-03-10",
                "period": 1,
                "student_id": data["student"].id,
                "status": "P",
            },
        )
        assert json.loads(r.content)["status"] == "L"

        r = c.post(
            reverse("save_attendance_cell"),
            {
                "class_id": data["klass"].id,
                "date": "2026-03-10",
                "period": 1,
                "student_id": data["student"].id,
                "status": "PRM",
            },
        )
        assert json.loads(r.content)["status"] == ""
        assert (
            AttendanceRecord.objects.filter(
                register__school_class=data["klass"],
                register__date=date(2026, 3, 10),
                register__period=1,
                student=data["student"],
            ).count()
            == 0
        )

    def test_conduct_config_get_post(self, data):
        c = Client()
        c.login(username="admin", password="pass")

        r = c.get(reverse("conduct_config"))
        assert r.status_code == 200
        assert "min_ua_warning" in r.content.decode()

        post = {}
        for ct in ["warning", "reprimand", "suspension", "dismissal"]:
            post.update(
                {
                    f"min_ua_{ct}": "5",
                    f"min_ja_{ct}": "2",
                    f"min_lat_{ct}": "3",
                    f"min_ph_{ct}": "2.5",
                }
            )
        r = c.post(reverse("conduct_config"), post)
        assert r.status_code == 302
        t = ConductThreshold.objects.get(school=data["school"], conduct_type="warning")
        assert t.min_unjustified_abs == 5
        assert t.min_punishment_hours == Decimal("2.5")

    def test_summary_page_has_thresholds(self, data):
        ConductThreshold.objects.create(
            school=data["school"], conduct_type="warning", min_unjustified_abs=6
        )
        c = Client()
        c.login(username="admin", password="pass")
        r = c.get(
            reverse("discipline_summary"),
            {"class_id": data["klass"].id, "term_id": data["term"].id},
        )
        assert r.status_code == 200
        body = r.content.decode()
        assert reverse("conduct_config") in body
        assert "Conduct Thresholds" in body
        assert "threshold-item" in body

    def test_class_master_dashboard_stats(self, data):
        from datetime import timedelta

        License.objects.create(
            product_key="OC-abc-test",
            school=data["school"],
            school_name="S",
            expires_at=date.today() + timedelta(days=30),
        )
        teacher = Teacher.objects.create(
            school=data["school"],
            first_name="Jane",
            last_name="Doe",
            teacher_code="CM9",
        )
        TeacherAssignment.objects.create(
            teacher=teacher,
            school_class=data["klass"],
            subject=data["subject"],
            is_class_master=True,
        )
        u = User.objects.create_user(username="CM9", password="pass")
        UserProfile.objects.create(user=u, school=data["school"], role="class_master")
        c = Client()
        c.login(username="CM9", password="pass")
        r = c.get(reverse("dashboard"))
        assert r.status_code == 200
        body = r.content.decode()
        assert "Pending Discipline" in body
        assert reverse("mark_entry_select") in body
        assert reverse("attendance_entry") in body


@pytest.mark.django_db
class TestAttendanceBatch:
    def _post(self, c, data, status="P", targets=None, extra=None):
        payload = {
            "class_id": data["klass"].id,
            "date": "2026-03-10",
            "status": status,
            "targets": targets or [[data["student"].id, p] for p in (1, 2, 3)],
        }
        if extra:
            payload.update(extra)
        return c.post(
            reverse("save_attendance_batch"),
            json.dumps(payload),
            content_type="application/json",
        )

    def test_batch_creates_all_records_in_one_request(self, data):
        c = Client()
        c.login(username="admin", password="pass")

        r = self._post(c, data)

        assert r.status_code == 200
        payload = json.loads(r.content)
        assert payload["saved"] is True
        assert payload["count"] == 3
        assert payload["status"] == "P"
        assert payload["summary"]["present"] == 3
        records = AttendanceRecord.objects.filter(
            register__school_class=data["klass"],
            register__date=date(2026, 3, 10),
            student=data["student"],
        )
        assert records.count() == 3
        assert {rec.register.period for rec in records} == {1, 2, 3}
        assert {rec.status for rec in records} == {"P"}

    def test_batch_updates_existing_without_duplicates(self, data):
        c = Client()
        c.login(username="admin", password="pass")

        r = self._post(c, data, status="A")

        assert r.status_code == 200
        records = AttendanceRecord.objects.filter(
            register__school_class=data["klass"],
            register__date=date(2026, 3, 10),
            student=data["student"],
        )
        assert records.count() == 3
        assert {rec.status for rec in records} == {"A"}

    def test_batch_ignores_unknown_students_and_periods(self, data):
        c = Client()
        c.login(username="admin", password="pass")

        r = self._post(
            c,
            data,
            targets=[[9999, 1], [data["student"].id, 99], [data["student"].id, 2]],
        )

        payload = json.loads(r.content)
        assert payload["saved"] is True
        assert payload["count"] == 1
        assert AttendanceRecord.objects.count() == 1
        assert AttendanceRecord.objects.first().register.period == 2

    def test_batch_rejects_invalid_status(self, data):
        c = Client()
        c.login(username="admin", password="pass")

        r = self._post(c, data, status="XX")

        assert r.status_code == 400
        assert AttendanceRecord.objects.count() == 0

    def test_batch_forbidden_without_manage_rights(self, data):
        teacher_user = User.objects.create_user(username="plain", password="pass")
        UserProfile.objects.create(
            user=teacher_user, school=data["school"], role="teacher"
        )
        c = Client()
        c.login(username="plain", password="pass")

        r = self._post(c, data)

        assert r.status_code == 403
        assert AttendanceRecord.objects.count() == 0
