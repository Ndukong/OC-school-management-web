"""View/UI tests for the timetable module (hub, wizard, views, exports)."""

from datetime import time as time_type

import pytest
from django.test import Client, override_settings
from django.urls import reverse

from core.models import (
    PeriodSlot,
    Subject,
    Teacher,
    Timetable,
    TimetableConfig,
    TimetableEntry,
)
from tests.conftest import requires_pdf
from tests.factories import (
    PASSWORD,
    login_client,
    make_admin,
    make_class,
    make_school_with_license,
    make_term,
    make_user,
)

FAST_SOLVER = override_settings(TIMETABLE_SOLVER_TIME_LIMIT=2)


def _make_teacher(school, code="TT1") -> Teacher:
    return Teacher.objects.create(
        school=school, first_name="Tim", last_name="Table", teacher_code=code
    )


def _make_config(school, **kwargs) -> TimetableConfig:
    defaults = {
        "school": school,
        "academic_year_start": 2026,
        "academic_year_end": 2027,
        "days": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
        "assembly_day": "Monday",
        "assembly_duration_periods": 0,
        "is_active": True,
    }
    defaults.update(kwargs)
    return TimetableConfig.objects.create(**defaults)


def _add_slots(config, count=3) -> list[PeriodSlot]:
    slots = []
    for i in range(1, count + 1):
        slots.append(
            PeriodSlot.objects.create(
                config=config,
                slot_number=i,
                slot_type="teaching",
                label=f"Period {i}",
                start_time=time_type(7, 30 + i),
                end_time=time_type(8, 10 + i),
                can_start_double=i < count,
            )
        )
    return slots


def _make_timetable(config, **kwargs) -> Timetable:
    defaults = {"config": config, "name": "Test Timetable", "status": "completed"}
    defaults.update(kwargs)
    return Timetable.objects.create(**defaults)


@pytest.fixture
def setup():
    school, _ = make_school_with_license("Timetable High", "TT-1")
    admin = make_admin("tt_admin", school)
    teacher_user = make_user("tt_teacher", school=school, role="teacher")
    make_term(school)
    return {
        "school": school,
        "admin": admin.username,
        "teacher": teacher_user.username,
    }


def _login(username):
    return login_client(username, PASSWORD)


# --- Access control -------------------------------------------------------


@pytest.mark.django_db
class TestTimetableAccess:
    def test_hub_requires_login(self):
        resp = Client().get(reverse("timetable_hub"))
        assert resp.status_code == 302
        assert "/login/" in resp["Location"]

    def test_hub_renders_for_admin(self, setup):
        resp = _login(setup["admin"]).get(reverse("timetable_hub"))
        assert resp.status_code == 200
        assert b"Timetable" in resp.content

    def test_teacher_without_published_redirects_to_dashboard(self, setup):
        resp = _login(setup["teacher"]).get(reverse("timetable_hub"))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("dashboard")

    def test_teacher_redirected_to_published_timetable(self, setup):
        config = _make_config(setup["school"])
        published = _make_timetable(config, status="published")
        resp = _login(setup["teacher"]).get(reverse("timetable_hub"))
        assert resp.status_code == 302
        assert resp["Location"] == reverse("timetable_master", args=[published.pk])

    def test_teacher_forbidden_on_config_wizard(self, setup):
        resp = _login(setup["teacher"]).get(reverse("timetable_config_create"))
        assert resp.status_code == 403

    def test_teacher_forbidden_on_export_excel(self, setup):
        config = _make_config(setup["school"])
        timetable = _make_timetable(config)
        resp = _login(setup["teacher"]).get(
            reverse("timetable_export_excel", args=[timetable.pk])
        )
        assert resp.status_code == 403


# --- Configuration wizard -------------------------------------------------


@pytest.mark.django_db
class TestConfigWizard:
    def test_create_page_renders(self, setup):
        resp = _login(setup["admin"]).get(reverse("timetable_config_create"))
        assert resp.status_code == 200
        assert b"Basic Setup" in resp.content

    def test_save_basic_creates_config(self, setup):
        client = _login(setup["admin"])
        resp = client.post(
            reverse("timetable_config_create"),
            {
                "action": "save_basic",
                "academic_year_start": 2026,
                "days": ["Monday", "Tuesday", "Wednesday"],
                "assembly_day": "Monday",
                "assembly_duration_periods": 1,
            },
        )
        assert resp.status_code == 302
        config = TimetableConfig.objects.get(school=setup["school"])
        assert config.days == ["Monday", "Tuesday", "Wednesday"]
        assert config.is_active is True

    def test_save_slots_creates_slots_and_doubles(self, setup):
        config = _make_config(setup["school"])
        client = _login(setup["admin"])
        resp = client.post(
            reverse("timetable_config_edit", args=[config.pk]),
            {
                "action": "save_slots",
                "slot_count": 3,
                "slot_type_1": "teaching",
                "slot_label_1": "Period 1",
                "slot_start_1": "07:30",
                "slot_end_1": "08:10",
                "slot_type_2": "break",
                "slot_label_2": "Break",
                "slot_start_2": "08:10",
                "slot_end_2": "08:30",
                "slot_type_3": "teaching",
                "slot_label_3": "Period 2",
                "slot_start_3": "08:30",
                "slot_end_3": "09:10",
            },
        )
        assert resp.status_code == 302
        slots = PeriodSlot.objects.filter(config=config)
        assert slots.count() == 3
        # Slot 1 is teaching but slot 2 is a break -> cannot start a double.
        p1 = slots.get(slot_number=1)
        assert p1.can_start_double is False

    def test_requirements_saved_via_wizard(self, setup):
        config = _make_config(setup["school"])
        school_class = make_class(setup["school"], "Form 1", "R1", 1)
        subject = Subject.objects.create(
            school=setup["school"], name="Math", code="MAT"
        )
        from core.models import ClassSubject

        ClassSubject.objects.create(
            school_class=school_class, subject=subject, coefficient=2
        )
        client = _login(setup["admin"])
        resp = client.post(
            reverse("timetable_config_edit", args=[config.pk]),
            {
                "action": "save_requirements",
                f"req_{school_class.pk}_{subject.pk}_periods": "3",
                f"req_{school_class.pk}_{subject.pk}_doubles": "1",
            },
        )
        assert resp.status_code == 302
        from core.models import SubjectPeriodRequirement

        assert SubjectPeriodRequirement.objects.filter(config=config).exists()


# --- Generation -----------------------------------------------------------


@pytest.mark.django_db
class TestGeneration:
    @FAST_SOLVER
    def test_generate_without_requirements_shows_error(self, setup):
        config = _make_config(setup["school"])
        client = _login(setup["admin"])
        resp = client.post(reverse("timetable_generate", args=[config.pk]), follow=True)
        assert resp.status_code == 200
        assert b"requirements" in resp.content.lower()

    @FAST_SOLVER
    def test_generate_creates_timetable(self, setup, monkeypatch):
        # Run the solver synchronously so the test DB transaction is not shared
        # with a daemon thread (which would deadlock on SQLite).
        import core.views.timetable as ttv
        from core.models import (
            ClassSubject,
            SubjectPeriodRequirement,
            TeacherAssignment,
        )

        class _SyncThread:
            def __init__(self, target=None, args=(), daemon=None, **kw):
                self._target = target
                self._args = args

            def start(self):
                self._target(*self._args)

        monkeypatch.setattr(ttv.threading, "Thread", _SyncThread)

        school = setup["school"]
        config = _make_config(school)
        _add_slots(config, 3)
        school_class = make_class(school, "Form 1", "T1", 1)
        subject = Subject.objects.create(school=school, name="Math", code="MAT")
        ClassSubject.objects.create(
            school_class=school_class, subject=subject, coefficient=2
        )
        teacher = _make_teacher(school)
        TeacherAssignment.objects.create(
            teacher=teacher, school_class=school_class, subject=subject
        )
        SubjectPeriodRequirement.objects.create(
            config=config,
            school_class=school_class,
            subject=subject,
            periods_per_week=2,
        )
        client = _login(setup["admin"])
        resp = client.post(reverse("timetable_generate", args=[config.pk]))
        assert resp.status_code == 302
        assert Timetable.objects.filter(config=config).exists()

    def test_generation_status_partial(self, setup):
        config = _make_config(setup["school"])
        timetable = _make_timetable(config, status="generating")
        resp = _login(setup["admin"]).get(
            reverse("timetable_generation_status", args=[config.pk])
        )
        assert resp.status_code == 200
        assert b"Generating" in resp.content
        assert timetable.pk  # sanity


# --- Viewing --------------------------------------------------------------


@pytest.mark.django_db
class TestTimetableViews:
    def test_master_view_renders_grid(self, setup):
        config = _make_config(setup["school"])
        timetable = _make_timetable(config)
        with override_settings():
            resp = _login(setup["admin"]).get(
                reverse("timetable_master", args=[timetable.pk])
            )
        assert resp.status_code == 200
        assert b"Timetable" in resp.content

    def test_teacher_cannot_see_unpublished_master(self, setup):
        config = _make_config(setup["school"])
        timetable = _make_timetable(config, status="completed")
        resp = _login(setup["teacher"]).get(
            reverse("timetable_master", args=[timetable.pk])
        )
        assert resp.status_code == 403

    def test_class_view_renders(self, setup):
        config = _make_config(setup["school"])
        timetable = _make_timetable(config)
        school_class = make_class(setup["school"], "Form 1", "C1", 1)
        resp = _login(setup["admin"]).get(
            reverse("timetable_class", args=[timetable.pk, school_class.pk])
        )
        assert resp.status_code == 200

    def test_teacher_view_own_schedule(self, setup):
        config = _make_config(setup["school"])
        timetable = _make_timetable(config)
        teacher = _make_teacher(setup["school"], "TS1")
        from core.models import UserProfile

        profile = UserProfile.objects.get(user__username=setup["teacher"])
        profile.teacher = teacher
        profile.save()
        resp = _login(setup["teacher"]).get(
            reverse("timetable_my_schedule", args=[timetable.pk])
        )
        assert resp.status_code == 200

    def test_room_view_renders(self, setup):
        config = _make_config(setup["school"])
        timetable = _make_timetable(config)
        resp = _login(setup["admin"]).get(
            reverse("timetable_room_view", args=[timetable.pk])
        )
        assert resp.status_code == 200

    def test_stats_view_renders(self, setup):
        config = _make_config(setup["school"])
        timetable = _make_timetable(config)
        resp = _login(setup["admin"]).get(
            reverse("timetable_stats", args=[timetable.pk])
        )
        assert resp.status_code == 200


# --- Manual editing -------------------------------------------------------


@pytest.mark.django_db
class TestManualEditing:
    def _entry(self, setup):
        config = _make_config(setup["school"])
        timetable = _make_timetable(config)
        slots = _add_slots(config, 3)
        school_class = make_class(setup["school"], "Form 1", "E1", 1)
        subject = Subject.objects.create(school=setup["school"], name="Sci", code="SCI")
        teacher = _make_teacher(setup["school"], "TE1")
        return TimetableEntry.objects.create(
            timetable=timetable,
            day="Tuesday",
            period_slot=slots[0],
            school_class=school_class,
            subject=subject,
            teacher=teacher,
        )

    def test_edit_page_renders(self, setup):
        entry = self._entry(setup)
        resp = _login(setup["admin"]).get(
            reverse("timetable_edit", args=[entry.timetable.pk])
        )
        assert resp.status_code == 200

    def test_lock_toggles(self, setup):
        entry = self._entry(setup)
        client = _login(setup["admin"])
        resp = client.post(reverse("timetable_lock_entry", args=[entry.pk]))
        assert resp.status_code == 200
        entry.refresh_from_db()
        assert entry.is_locked is True

    def test_swap_moves_entry(self, setup):
        entry = self._entry(setup)
        other_slot = PeriodSlot.objects.get(
            config=entry.timetable.config, slot_number=2
        )
        client = _login(setup["admin"])
        resp = client.post(
            reverse("timetable_swap", args=[entry.timetable.pk]),
            {
                "action": "move",
                "entry_a": entry.pk,
                "new_day": "Wednesday",
                "new_slot": other_slot.pk,
            },
        )
        assert resp.status_code == 200
        entry.refresh_from_db()
        assert entry.day == "Wednesday"
        assert entry.period_slot_id == other_slot.pk

    def test_publish_sets_status(self, setup):
        entry = self._entry(setup)
        client = _login(setup["admin"])
        resp = client.post(reverse("timetable_publish", args=[entry.timetable.pk]))
        assert resp.status_code == 302
        entry.timetable.refresh_from_db()
        assert entry.timetable.status == "published"

    def test_delete_non_published(self, setup):
        entry = self._entry(setup)
        pk = entry.timetable.pk
        client = _login(setup["admin"])
        resp = client.post(reverse("timetable_delete", args=[pk]))
        assert resp.status_code == 302
        assert not Timetable.objects.filter(pk=pk).exists()

    def test_delete_published_blocked(self, setup):
        entry = self._entry(setup)
        entry.timetable.publish()
        pk = entry.timetable.pk
        client = _login(setup["admin"])
        client.post(reverse("timetable_delete", args=[pk]))
        assert Timetable.objects.filter(pk=pk).exists()


# --- Exports --------------------------------------------------------------


@pytest.mark.django_db
class TestTimetableExports:
    def test_excel_export_content_type(self, setup):
        config = _make_config(setup["school"])
        timetable = _make_timetable(config)
        _add_slots(config, 2)
        resp = _login(setup["admin"]).get(
            reverse("timetable_export_excel", args=[timetable.pk])
        )
        assert resp.status_code == 200
        assert "spreadsheetml" in resp["Content-Type"]
        assert resp.content[:2] == b"PK"

    @requires_pdf
    def test_master_pdf_export(self, setup):
        config = _make_config(setup["school"])
        timetable = _make_timetable(config)
        _add_slots(config, 2)
        resp = _login(setup["admin"]).get(
            reverse("timetable_export_master_pdf", args=[timetable.pk])
        )
        assert resp.status_code == 200
        assert resp["Content-Type"] == "application/pdf"
        assert resp.content[:4] == b"%PDF"
