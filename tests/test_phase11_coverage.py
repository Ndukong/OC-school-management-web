"""Phase 11 (part 2): Coverage closure tests.

Targets modules below 80%: mark_sheet, results_summary, student_id, teachers,
api/views, backup scheduling, notifications provider paths, BaseReport,
management commands, and admin actions.
"""

import io
import os
from datetime import date, timedelta
from decimal import Decimal
from io import BytesIO

import pytest
from django.contrib.auth.models import User
from django.core import management
from django.test import Client
from django.urls import reverse

from core.admin import compute_class_results, compute_term_results_action
from core.models import (
    AcademicTerm,
    ClassSubject,
    Competency,
    CompetencyScore,
    ConductThreshold,
    DisciplineSummary,
    School,
    SchoolClass,
    SMSConfig,
    Student,
    StudentEnrollment,
    Subject,
    SubjectAverage,
    Teacher,
    TeacherAssignment,
    TermResult,
    UserProfile,
)


@pytest.fixture
def school():
    return School.objects.create(
        name_en="Coverage School",
        matricule="COV01",
        region_en="Centre",
        division_en="Mfoundi",
    )


@pytest.fixture
def term(school):
    return AcademicTerm.objects.create(
        school=school, term_number=1, year_start=2025, year_end=2026, is_current=True
    )


@pytest.fixture
def sc(school):
    return SchoolClass.objects.create(
        school=school, name="Form 1", code="F1", form_level=1, promotion_mark=10.0
    )


@pytest.fixture
def subj(school):
    return Subject.objects.create(school=school, name="Math", code="MAT")


@pytest.fixture
def admin_user(school):
    u = User.objects.create_user(
        username="covadmin", password="pass", is_superuser=True
    )
    UserProfile.objects.create(user=u, school=school, role="admin")
    return u


@pytest.fixture
def active_license(school):
    from core.models import License

    lic, _ = License.objects.get_or_create(
        product_key="OC-cov-active",
        defaults={
            "school": school,
            "school_name": "Coverage School",
            "expires_at": date.today() + timedelta(days=60),
            "status": "active",
        },
    )
    return lic


@pytest.fixture
def student(school):
    return Student.objects.create(
        school=school,
        first_name="S1",
        sex="M",
        unique_id="888000111",
        date_of_birth=date(2010, 1, 1),
        place_of_birth="D",
        guardian_name="G",
        guardian_contact="670000111",
        division_of_origin="W",
        region_of_origin="L",
    )


def make_enrolled_student(school, sc, term, name, sex, unique_id):
    s = Student.objects.create(
        school=school,
        first_name=name,
        sex=sex,
        unique_id=unique_id,
        date_of_birth=date(2010, 1, 1),
        place_of_birth="D",
        guardian_name="G",
        division_of_origin="W",
        region_of_origin="L",
    )
    StudentEnrollment.objects.create(student=s, school_class=sc, academic_term=term)
    return s


def login_client(user):
    c = Client()
    c.login(username=user.username, password="pass")
    return c


# ═══════════════════════════════════════════════════════════════════════════
# MarkSheet
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestMarkSheet:
    def test_get_context_data_empty(self, school, sc, term):
        from core.utils.mark_sheet import MarkSheet

        ms = MarkSheet(sc, term, school)
        ctx = ms.get_context_data()
        assert ctx["school_class"] == sc
        assert ctx["term"] == term
        assert ctx["rows"] == []

    def test_get_context_data_with_data(self, school, sc, term, subj):
        from core.utils.mark_sheet import MarkSheet

        ClassSubject.objects.create(school_class=sc, subject=subj, coefficient=4)
        s = make_enrolled_student(school, sc, term, "AA", "M", "888000222")
        SubjectAverage.objects.create(
            student=s, subject=subj, academic_term=term, average=Decimal("15.00")
        )
        ms = MarkSheet(sc, term, school)
        ctx = ms.get_context_data()
        assert len(ctx["rows"]) == 1
        assert ctx["rows"][0]["average"] == Decimal("15.00")
        assert ctx["rows"][0]["remark"] in ("Passed", "Failed")
        assert ctx["rows"][0]["rank"] in ("1st", "2nd", "3rd")

    def test_filename(self, school, sc, term):
        from core.utils.mark_sheet import MarkSheet

        ms = MarkSheet(sc, term, school)
        assert "F1" in ms.filename()


# ═══════════════════════════════════════════════════════════════════════════
# ResultsSummary
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestResultsSummary:
    def test_context_empty(self, school, sc, term):
        from core.utils.results_summary import ResultsSummary

        rs = ResultsSummary(sc, term, school)
        ctx = rs.get_context_data()
        assert ctx["enrolment_total"] == 0
        assert ctx["num_sat"] == 0
        assert ctx["class_average"] == Decimal("0.00")
        assert ctx["is_annual"] is False

    def test_context_with_results(self, school, sc, term):
        from core.utils.results_summary import ResultsSummary

        s_m = make_enrolled_student(school, sc, term, "MM", "M", "888000333")
        s_f = make_enrolled_student(school, sc, term, "FF", "F", "888000334")
        TermResult.objects.create(
            student=s_m, academic_term=term, average=Decimal("15.00")
        )
        TermResult.objects.create(
            student=s_f, academic_term=term, average=Decimal("8.00")
        )
        rs = ResultsSummary(sc, term, school)
        ctx = rs.get_context_data()
        assert ctx["enrolment_total"] == 2
        assert ctx["num_sat"] == 2
        assert ctx["num_passed"] == 1
        assert ctx["enrolment_m"] == 1
        assert ctx["enrolment_f"] == 1
        assert ctx["success_rate"] == Decimal("50.0")
        assert len(ctx["top3"]) == 2


# ═══════════════════════════════════════════════════════════════════════════
# Student ID rendering
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestStudentID:
    def test_render_single_id_page(self, school, student):
        from core.utils.student_id import render_single_id_page

        html = render_single_id_page(1, student, school)
        assert "888000111" in html  # matricule shown

    def test_render_full_set_html(self, school):
        from core.utils.student_id import render_full_set_html

        students = []
        for i in range(4):
            students.append(
                Student.objects.create(
                    school=school,
                    first_name=f"ID{i}",
                    sex="M",
                    unique_id=f"99900000{i}",
                    date_of_birth=date(2010, 1, 1),
                    place_of_birth="D",
                    guardian_name="G",
                    division_of_origin="W",
                    region_of_origin="L",
                )
            )
        html = render_full_set_html(students, school)
        assert isinstance(html, str)
        assert "999000000" in html

    def test_render_full_set_with_custom_context(self, school):
        from core.utils.student_id import render_full_set_html

        students = []
        for i in range(4):
            students.append(
                Student.objects.create(
                    school=school,
                    first_name=f"IDX{i}",
                    sex="F",
                    unique_id=f"97700000{i}",
                    date_of_birth=date(2010, 1, 1),
                    place_of_birth="D",
                    guardian_name="G",
                    division_of_origin="W",
                    region_of_origin="L",
                )
            )
        html = render_full_set_html(students, school, {"academic_year": "2024/2025"})
        assert isinstance(html, str)


# ═══════════════════════════════════════════════════════════════════════════
# API views
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAPIViews:
    def test_api_assignments_teacher_not_found(self, school, admin_user):
        c = login_client(admin_user)
        r = c.get(reverse("api_assignments"))
        assert r.status_code == 404

    def test_api_assignments_with_teacher(self, school, sc, subj, term):
        u = User.objects.create_user(username="t_api", password="pass")
        UserProfile.objects.create(user=u, school=school, role="teacher")
        t = Teacher.objects.create(school=school, first_name="AT", last_name="API")
        UserProfile.objects.filter(user=u).update(teacher=t)
        TeacherAssignment.objects.create(
            teacher=t, school_class=sc, subject=subj, is_active=True
        )
        c = login_client(u)
        r = c.get(reverse("api_assignments"))
        assert r.status_code == 200
        data = r.json()
        assert len(data["assignments"]) == 1
        assert data["current_term"] is not None

    def test_api_class_subject(self, school, sc, subj, term, student):
        ClassSubject.objects.create(school_class=sc, subject=subj, coefficient=4)
        StudentEnrollment.objects.create(
            student=student, school_class=sc, academic_term=term
        )
        u = User.objects.create_user(username="t_api2", password="pass")
        UserProfile.objects.create(user=u, school=school, role="teacher")
        t = Teacher.objects.create(school=school, first_name="BT", last_name="API")
        UserProfile.objects.filter(user=u).update(teacher=t)
        TeacherAssignment.objects.create(teacher=t, school_class=sc, subject=subj)
        c = login_client(u)
        r = c.get(reverse("api_class_subject", args=[sc.pk, subj.pk]))
        assert r.status_code == 200
        data = r.json()
        assert data["class"]["id"] == sc.pk
        assert len(data["students"]) == 1

    def test_api_class_subject_not_found(self, school, admin_user):
        c = login_client(admin_user)
        r = c.get(reverse("api_class_subject", args=[9999, 9999]))
        assert r.status_code == 404

    def test_api_save_scores(self, school, sc, subj, term, student):
        ClassSubject.objects.create(school_class=sc, subject=subj, coefficient=4)
        StudentEnrollment.objects.create(
            student=student, school_class=sc, academic_term=term
        )
        comp = Competency.objects.create(
            subject=subj, term=term, form_level=1, sort_order=1, description="C"
        )
        u = User.objects.create_user(username="t_api3", password="pass")
        UserProfile.objects.create(user=u, school=school, role="teacher")
        t = Teacher.objects.create(school=school, first_name="CT", last_name="API")
        UserProfile.objects.filter(user=u).update(teacher=t)
        TeacherAssignment.objects.create(teacher=t, school_class=sc, subject=subj)
        c = login_client(u)

        r = c.post(
            reverse("api_save_scores", args=[sc.pk, subj.pk]),
            data=[
                {"student_id": student.pk, "competency_id": comp.pk, "score": "15.5"},
            ],
            content_type="application/json",
        )
        assert r.status_code == 200
        assert r.json()["saved"] == 1
        assert CompetencyScore.objects.filter(student=student, competency=comp).exists()

    def test_api_save_scores_delete(self, school, sc, subj, term, student):
        ClassSubject.objects.create(school_class=sc, subject=subj, coefficient=4)
        StudentEnrollment.objects.create(
            student=student, school_class=sc, academic_term=term
        )
        comp = Competency.objects.create(
            subject=subj, term=term, form_level=1, sort_order=1, description="C"
        )
        CompetencyScore.objects.create(
            student=student, competency=comp, academic_term=term, score=Decimal("10.0")
        )
        u = User.objects.create_user(username="t_api4", password="pass")
        UserProfile.objects.create(user=u, school=school, role="teacher")
        t = Teacher.objects.create(school=school, first_name="DT", last_name="API")
        UserProfile.objects.filter(user=u).update(teacher=t)
        TeacherAssignment.objects.create(teacher=t, school_class=sc, subject=subj)
        c = login_client(u)
        r = c.post(
            reverse("api_save_scores", args=[sc.pk, subj.pk]),
            data=[
                {"student_id": student.pk, "competency_id": comp.pk, "score": None},
            ],
            content_type="application/json",
        )
        assert r.status_code == 200
        assert not CompetencyScore.objects.filter(
            student=student, competency=comp
        ).exists()


# ═══════════════════════════════════════════════════════════════════════════
# Backup scheduling + notifications provider paths
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestBackupScheduling:
    def test_generate_scheduled_task_script(self):
        from core.utils.backup import generate_scheduled_task_script

        path = generate_scheduled_task_script()
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert "create_backup" in content

    def test_generate_scheduled_task_xml(self):
        from core.utils.backup import generate_scheduled_task_xml

        path = generate_scheduled_task_xml()
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert "<Task" in content

    def test_backup_history_properties(self, admin_user):
        from core.models.backup import BackupHistory

        h = BackupHistory.objects.create(
            filename="test.zip",
            filepath="/tmp/test.zip",
            file_size=1024,
            backup_type="database",
            created_by=admin_user,
        )
        assert h.size_display is not None


@pytest.mark.django_db
class TestSMSProviderPaths:
    def test_twilio_missing_credentials(self, school):
        cfg = SMSConfig.objects.create(
            school=school,
            provider="twilio",
            api_key="",
            api_secret="",
            sender_id="",
            is_active=True,
        )
        from core.utils.notifications import process_sms_queue, queue_sms

        queue_sms(cfg, "670000001", "hi")
        sent, failed = process_sms_queue()
        assert sent == 0
        assert failed == 0

    def test_unknown_provider_fails(self, school):
        cfg = SMSConfig.objects.create(
            school=school,
            provider="unknown",
            is_active=True,
        )
        from core.utils.notifications import _send_sms, process_sms_queue, queue_sms

        sms = queue_sms(cfg, "670000001", "hi")
        assert _send_sms(sms) is False
        # With max_retries=1 the first failure marks it failed
        sms.max_retries = 1
        sms.retry_count = 0
        sms.save()
        sent, failed = process_sms_queue()
        assert sent == 0
        assert failed == 1
        sms.refresh_from_db()
        assert sms.status == "failed"

    def test_retry_and_fail(self, school):
        cfg = SMSConfig.objects.create(school=school, provider="manual", is_active=True)
        from core.utils.notifications import process_sms_queue, queue_sms

        sms = queue_sms(cfg, "670000001", "hi")
        sms.max_retries = 2
        sms.retry_count = 2
        sms.save()
        sent, failed = process_sms_queue()
        assert sent == 1  # manual provider always succeeds

    def test_sms_message_str(self, school):
        cfg = SMSConfig.objects.create(school=school, provider="manual", is_active=True)
        from core.utils.notifications import queue_sms

        sms = queue_sms(cfg, "670000001", "hello")
        assert "670000001" in str(sms)


# ═══════════════════════════════════════════════════════════════════════════
# Teacher dashboard + admin actions
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestTeacherDashboard:
    def test_teacher_dashboard_renders(self, school, admin_user, active_license):
        c = login_client(admin_user)
        r = c.get(reverse("teacher_dashboard"))
        assert r.status_code == 200

    def test_teacher_dashboard_assignments(
        self, school, sc, subj, term, active_license
    ):
        u = User.objects.create_user(username="tdash", password="pass")
        UserProfile.objects.create(user=u, school=school, role="teacher")
        t = Teacher.objects.create(school=school, first_name="D", last_name="Dash")
        UserProfile.objects.filter(user=u).update(teacher=t)
        TeacherAssignment.objects.create(teacher=t, school_class=sc, subject=subj)
        c = login_client(u)
        r = c.get(reverse("teacher_dashboard"))
        assert r.status_code == 200
        assert "Math" in r.content.decode()


@pytest.mark.django_db
class TestAdminActions:
    def test_compute_class_results_action(
        self, school, sc, term, admin_user, active_license
    ):
        from django.contrib.messages.storage.cookie import CookieStorage
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get("/admin/core/schoolclass/")
        request.user = admin_user
        request._messages = CookieStorage(request)
        qs = SchoolClass.objects.filter(pk=sc.pk)
        compute_class_results(None, request, qs)

    def test_compute_term_results_action(
        self, school, sc, term, admin_user, active_license
    ):
        from django.contrib.messages.storage.cookie import CookieStorage
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.get("/admin/core/academicterm/")
        request.user = admin_user
        request._messages = CookieStorage(request)
        qs = AcademicTerm.objects.filter(pk=term.pk)
        compute_term_results_action(None, request, qs)


# ═══════════════════════════════════════════════════════════════════════════
# Management commands
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestManagementCommands:
    def test_create_backup_command(self):
        out = io.StringIO()
        management.call_command("create_backup", stdout=out)
        assert "Backup created" in out.getvalue()

    def test_create_backup_command_database(self):
        out = io.StringIO()
        management.call_command("create_backup", "--type", "database", stdout=out)
        assert "Backup created" in out.getvalue()

    def test_generate_license_command(self):
        out = io.StringIO()
        management.call_command(
            "generate_license", "Test School", "--days", "30", stdout=out
        )
        assert "Product Key" in out.getvalue()

    def test_compute_results_command(self, school, sc, term, subj):
        s = make_enrolled_student(school, sc, term, "CR", "M", "888000555")
        ClassSubject.objects.create(school_class=sc, subject=subj, coefficient=4)
        comp = Competency.objects.create(
            subject=subj, term=term, form_level=1, sort_order=1, description="C"
        )
        CompetencyScore.objects.create(
            student=s, competency=comp, academic_term=term, score=Decimal("14.0")
        )
        out = io.StringIO()
        management.call_command(
            "compute_results",
            "--class",
            "F1",
            "--school",
            str(school.pk),
            stdout=out,
        )
        assert TermResult.objects.filter(student=s, academic_term=term).exists()

    def test_compute_results_command_missing_class(self, school):
        from django.core.management.base import CommandError

        with pytest.raises(CommandError):
            management.call_command("compute_results", "--school", str(school.pk))

    def test_compute_results_command_bad_school(self):
        from django.core.management.base import CommandError

        with pytest.raises(CommandError):
            management.call_command(
                "compute_results", "--school", "99999", "--class", "F1"
            )

    def test_import_students_command_missing_file(self, school):
        from django.core.management.base import CommandError

        with pytest.raises(CommandError):
            management.call_command(
                "import_students",
                "--school",
                str(school.pk),
                "--file",
                "/nonexistent.xlsx",
            )

    def test_import_students_command_valid(self, school, sc, term):
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Name", "Register Number", "Sex", "Date of Birth", "Class"])
        ws.append(["Test Student", "999000111", "M", "10/05/2010", "F1"])
        buf = BytesIO()
        wb.save(buf)
        tmp_path = os.path.join(os.environ.get("TEMP", "/tmp"), "imp_test.xlsx")
        with open(tmp_path, "wb") as f:
            f.write(buf.getvalue())

        out = io.StringIO()
        management.call_command(
            "import_students",
            "--school",
            str(school.pk),
            "--file",
            tmp_path,
            stdout=out,
        )
        assert Student.objects.filter(unique_id="999000111").exists()
        os.remove(tmp_path)

    def test_import_competencies_command_missing_file(self, school):
        from django.core.management.base import CommandError

        with pytest.raises(CommandError):
            management.call_command(
                "import_competencies", "--file", "/nonexistent.xlsx"
            )


# ═══════════════════════════════════════════════════════════════════════════
# Conduct / discipline utils
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestDisciplineUtils:
    def test_conduct_threshold_defaults(self, school, sc):
        ct = ConductThreshold.objects.create(
            school=school,
            conduct_type="warning",
            min_unjustified_abs=3,
            min_lateness=6,
            min_punishment_hours=Decimal("2.0"),
        )
        assert ct.min_unjustified_abs == 3
        assert ct.min_lateness == 6
        assert "Warning" in str(ct)

    def test_discipline_summary_create(self, school, term, student):
        ds = DisciplineSummary.objects.create(
            student=student,
            academic_term=term,
            unjustified_abs_hours=Decimal("2.0"),
            lateness_count=3,
        )
        assert ds.lateness_count == 3


# ═══════════════════════════════════════════════════════════════════════════
# BaseReport
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestBaseReport:
    def test_render_html(self, school, sc, term):
        from core.utils.mark_sheet import MarkSheet

        ms = MarkSheet(sc, term, school)
        html = ms.render_html()
        assert isinstance(html, str)

    def test_filename_default(self):
        from core.utils.reports import BaseReport

        assert BaseReport().filename() == "report.pdf"

    def test_base_context_empty(self):
        from core.utils.reports import BaseReport

        assert BaseReport().get_context_data() == {}


# ═══════════════════════════════════════════════════════════════════════════
# Mark entry views + attendance entry
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestMarksAttendanceViews:
    def test_mark_entry_select_renders(self, school, admin_user):
        c = login_client(admin_user)
        r = c.get(reverse("mark_entry_select"))
        assert r.status_code == 200

    def test_mark_entry(self, school, sc, subj, term, admin_user):
        ClassSubject.objects.create(school_class=sc, subject=subj, coefficient=4)
        Competency.objects.create(
            subject=subj, term=term, form_level=1, sort_order=1, description="C"
        )
        c = login_client(admin_user)
        r = c.get(reverse("mark_entry", args=[sc.pk, subj.pk]))
        assert r.status_code in (200, 302)

    def test_attendance_entry_renders(self, school, admin_user):
        c = login_client(admin_user)
        r = c.get(reverse("attendance_entry"))
        assert r.status_code == 200
