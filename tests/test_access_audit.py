"""Access-matrix tests for mark sheets + audit trail behaviour."""

from datetime import date, timedelta

import pytest
from auditlog.models import LogEntry
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from core.models import (
    AcademicTerm,
    License,
    School,
    SchoolClass,
    Subject,
    Teacher,
    TeacherAssignment,
    UserProfile,
)

PASSWORD = "access-matrix-pass"


def _setup_class_with_staff():
    school = School.objects.create(
        name_en="Matrix High", matricule="MX-1", region_en="SW", division_en="Fako"
    )
    License.objects.create(
        product_key="OC-mx-1",
        school=school,
        school_name=school.name_en,
        max_students=500,
        expires_at=date.today() + timedelta(days=365),
        status="active",
    )
    klass = SchoolClass.objects.create(
        school=school, name="Form 1", code="F1", form_level=1
    )
    term = AcademicTerm.objects.create(
        school=school, term_number=1, year_start=2025, year_end=2026, is_current=True
    )
    subject = Subject.objects.create(school=school, name="Math", code="MAT")

    def make_user(username, role=None, teacher=None):
        user = User.objects.create_user(username=username, password=PASSWORD)
        UserProfile.objects.create(
            user=user, school=school, role=role or "teacher", teacher=teacher
        )
        return user

    master_teacher = Teacher.objects.create(
        school=school, first_name="Master", last_name="One", teacher_code="MX-M"
    )
    master = make_user("mx_master", role="class_master", teacher=master_teacher)
    TeacherAssignment.objects.create(
        teacher=master_teacher,
        school_class=klass,
        subject=subject,
        is_class_master=True,
        is_active=True,
    )

    subject_teacher = Teacher.objects.create(
        school=school, first_name="Teach", last_name="Assigned", teacher_code="MX-T"
    )
    assigned = make_user("mx_assigned", role="teacher", teacher=subject_teacher)
    TeacherAssignment.objects.create(
        teacher=subject_teacher,
        school_class=klass,
        subject=subject,
        is_active=True,
    )

    outsider_teacher = Teacher.objects.create(
        school=school, first_name="Other", last_name="Subject", teacher_code="MX-O"
    )
    unassigned = make_user("mx_outsider", role="teacher", teacher=outsider_teacher)

    admin = make_user("mx_admin", role="admin")

    return {
        "school": school,
        "klass": klass,
        "term": term,
        "master": master,
        "assigned": assigned,
        "unassigned": unassigned,
        "admin": admin,
    }


def _login(username):
    c = Client()
    assert c.login(username=username, password=PASSWORD)
    return c


@pytest.mark.django_db
class TestMarkSheetAccess:
    def test_master_previews_own_class(self):
        d = _setup_class_with_staff()
        c = _login(d["master"].username)
        r = c.get(reverse("preview_mark_sheet", args=[d["klass"].pk, d["term"].pk]))
        assert r.status_code == 200

    def test_assigned_teacher_previews(self):
        d = _setup_class_with_staff()
        c = _login(d["assigned"].username)
        r = c.get(reverse("preview_mark_sheet", args=[d["klass"].pk, d["term"].pk]))
        assert r.status_code == 200

    def test_unassigned_teacher_blocked(self):
        d = _setup_class_with_staff()
        c = _login(d["unassigned"].username)
        r = c.get(reverse("preview_mark_sheet", args=[d["klass"].pk, d["term"].pk]))
        assert r.status_code == 403

    def test_master_cannot_download(self):
        d = _setup_class_with_staff()
        c = _login(d["master"].username)
        r = c.get(reverse("download_mark_sheet", args=[d["klass"].pk, d["term"].pk]))
        assert r.status_code == 403

    def test_admin_can_download(self):
        d = _setup_class_with_staff()
        c = _login(d["admin"].username)
        r = c.get(reverse("download_mark_sheet", args=[d["klass"].pk, d["term"].pk]))
        assert r.status_code == 200


@pytest.mark.django_db
class TestAuditTrail:
    def test_login_is_logged(self, client):
        school = School.objects.create(
            name_en="Audit High",
            matricule="AU-1",
            region_en="SW",
            division_en="Fako",
        )
        user = User.objects.create_user(username="auditor", password=PASSWORD)
        UserProfile.objects.create(user=user, school=school, role="admin")

        client.login(username=user.username, password=PASSWORD)

        entry = LogEntry.objects.filter(actor=user).order_by("-timestamp").first()
        assert entry is not None
        changes = entry.changes if isinstance(entry.changes, dict) else {}
        assert changes.get("auth_event", {}).get("value") == "logged in"

    def test_audit_page_admin_ok_teacher_forbidden(self, client):
        school = School.objects.create(
            name_en="Audit High 2",
            matricule="AU-2",
            region_en="SW",
            division_en="Fako",
        )
        admin = User.objects.create_user(username="au_admin", password=PASSWORD)
        UserProfile.objects.create(user=admin, school=school, role="admin")
        teacher = User.objects.create_user(username="au_teacher", password=PASSWORD)
        UserProfile.objects.create(user=teacher, school=school, role="teacher")

        admin_client = client
        assert admin_client.login(username=admin.username, password=PASSWORD)
        assert admin_client.get(reverse("audit_log")).status_code == 200

        teacher_client = Client()
        assert teacher_client.login(username=teacher.username, password=PASSWORD)
        assert teacher_client.get(reverse("audit_log")).status_code == 403

    def test_tracked_model_change_creates_entry(self, db):
        school = School.objects.create(
            name_en="Track High",
            matricule="AU-3",
            region_en="SW",
            division_en="Fako",
        )
        klass = SchoolClass.objects.create(
            school=school, name="Form 2", code="F2", form_level=2
        )
        klass.name = "Form 2 Renamed"
        klass.save()

        update = LogEntry.objects.filter(
            object_id=str(klass.pk), action=LogEntry.Action.UPDATE
        ).order_by("-timestamp")
        assert update.exists()
        assert update.first().object_repr == "Form 2 Renamed"

    def test_failed_login_recorded_for_existing_user(self, client, db):
        school = School.objects.create(
            name_en="Audit High 3",
            matricule="AU-4",
            region_en="SW",
            division_en="Fako",
        )
        user = User.objects.create_user(username="au_fail", password=PASSWORD)
        UserProfile.objects.create(user=user, school=school, role="teacher")

        client.post(
            reverse("login"),
            {"username": user.username, "password": "totally-wrong"},
        )

        entry = LogEntry.objects.filter(actor=user).order_by("-timestamp").first()
        assert entry is not None
        changes = entry.changes if isinstance(entry.changes, dict) else {}
        assert changes.get("auth_event", {}).get("value") == "failed login"

    def test_audit_log_has_json_payload(self, client, db):
        """The changes column must stay machine-readable JSON for tooling."""
        school = School.objects.create(
            name_en="Audit High 4",
            matricule="AU-5",
            region_en="SW",
            division_en="Fako",
        )
        user = User.objects.create_user(username="au_json", password=PASSWORD)
        UserProfile.objects.create(user=user, school=school, role="admin")

        client.login(username=user.username, password=PASSWORD)

        entry = LogEntry.objects.filter(actor=user).order_by("-timestamp").first()
        decoded = entry.changes
        assert decoded["auth_event"]["value"] == "logged in"
