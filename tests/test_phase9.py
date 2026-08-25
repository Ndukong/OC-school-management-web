"""Phase 9: Backup, License, SMS, Notifications — comprehensive tests.

Tests:
  - Backup create/restore/download
  - License info, key generation, offline validation
  - SMS config, queue, process
  - Notifications create, read, unread count
"""

import json
import os
import zipfile
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.test import Client
from django.urls import reverse

from core.models import (
    AcademicTerm,
    License,
    Notification,
    School,
    SchoolClass,
    SMSConfig,
    SMSMessage,
    Student,
    UserProfile,
)
from core.models.backup import BackupHistory
from core.utils.backup import create_backup_archive, restore_backup_archive
from core.utils.notifications import (
    process_sms_queue,
    queue_sms,
    send_absence_notification,
    send_fee_reminder,
    send_report_ready_notification,
)


@pytest.fixture
def phase9_data():
    school = School.objects.create(
        name_en="Phase9 School",
        matricule="P9001",
        region_en="South",
        division_en="Meme",
    )
    sc = SchoolClass.objects.create(
        school=school, name="Form 1", code="F1", form_level=1
    )
    term = AcademicTerm.objects.create(
        school=school, term_number=1, year_start=2025, year_end=2026, is_current=True
    )
    student = Student.objects.create(
        school=school,
        first_name="Alice",
        sex="F",
        unique_id="999888777",
        date_of_birth=date(2010, 1, 1),
        place_of_birth="Buea",
        guardian_name="Guardian",
        guardian_contact="670000001",
        division_of_origin="Meme",
        region_of_origin="South",
    )

    license_obj = License.objects.create(
        product_key="OC-test1234-validkey",
        school_name="Phase9 School",
        max_students=500,
        max_devices=3,
        expires_at=date.today() + timedelta(days=365),
        status="active",
        activated_at=None,
        machine_id="test-machine-id",
        activation_count=1,
    )

    admin_user = User.objects.create_user(
        username="p9admin", password="pass", is_staff=True, is_superuser=True
    )
    UserProfile.objects.create(user=admin_user, school=school, role="admin")

    teacher_user = User.objects.create_user(username="p9teacher", password="pass")
    UserProfile.objects.create(user=teacher_user, school=school, role="teacher")

    sms_config = SMSConfig.objects.create(
        school=school,
        provider="manual",
        is_active=True,
        daily_limit=50,
    )

    def login(u):
        c = Client()
        c.login(username=u.username, password="pass")
        return c

    return {
        "school": school,
        "sc": sc,
        "term": term,
        "student": student,
        "license": license_obj,
        "admin": admin_user,
        "teacher": teacher_user,
        "sms_config": sms_config,
        "login": login,
    }


# ─── Backup Tests ──────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestBackupSystem:
    def test_create_backup_creates_file(self, phase9_data):
        history = create_backup_archive(
            user=phase9_data["admin"], notes="test", backup_type="database"
        )
        assert history.pk is not None
        assert os.path.exists(history.filepath)
        assert history.file_size > 0
        assert history.status == "created"
        assert history.backup_type == "database"

    def test_backup_contains_db(self, phase9_data):
        history = create_backup_archive(backup_type="database")
        with zipfile.ZipFile(history.filepath, "r") as zf:
            names = zf.namelist()
            assert "database/db.sqlite3" in names or "database/dumpdata.json" in names
            assert "backup_meta.json" in names

    def test_backup_management_renders(self, phase9_data):
        c = phase9_data["login"](phase9_data["admin"])
        r = c.get(reverse("backup_management"))
        assert r.status_code == 200
        assert "Backup Management" in r.content.decode()

    def test_create_backup_via_view(self, phase9_data):
        c = phase9_data["login"](phase9_data["admin"])
        r = c.post(
            reverse("backup_management"),
            {
                "action": "create",
                "backup_type": "database",
                "notes": "View test",
            },
        )
        assert r.status_code == 302
        assert BackupHistory.objects.filter(notes="View test").exists()

    def test_download_backup(self, phase9_data):
        history = create_backup_archive(backup_type="database")
        c = phase9_data["login"](phase9_data["admin"])
        r = c.get(reverse("download_backup", args=[history.pk]))
        assert r.status_code == 200
        assert r["Content-Type"] == "application/zip"

    def test_restore_backup(self, phase9_data):
        history = create_backup_archive(backup_type="database")
        success, msg = restore_backup_archive(history.pk)
        assert success is True
        assert "successfully" in msg.lower()
        history.refresh_from_db()
        assert history.status == "restored"

    def test_restore_nonexistent_backup(self):
        success, msg = restore_backup_archive(99999)
        assert success is False
        assert "not found" in msg.lower()

    def test_teacher_forbidden_from_backup(self, phase9_data):
        c = phase9_data["login"](phase9_data["teacher"])
        r = c.get(reverse("backup_management"))
        assert r.status_code == 403

    def test_generate_schedule_scripts(self, phase9_data):
        c = phase9_data["login"](phase9_data["admin"])
        r = c.post(reverse("backup_management"), {"action": "generate_schedule"})
        assert r.status_code == 302

    def test_backup_history_listed(self, phase9_data):
        create_backup_archive(notes="First backup", backup_type="database")
        create_backup_archive(notes="Second backup", backup_type="database")
        c = phase9_data["login"](phase9_data["admin"])
        r = c.get(reverse("backup_management"))
        html = r.content.decode()
        assert "First backup" in html
        assert "Second backup" in html


# ─── License Tests ─────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestLicenseSystem:
    def test_license_info_renders(self, phase9_data):
        c = phase9_data["login"](phase9_data["admin"])
        r = c.get(reverse("license_info"))
        assert r.status_code == 200
        html = r.content.decode()
        assert "Phase9 School" in html
        assert "Active" in html

    def test_generate_license_key_get(self, phase9_data):
        c = phase9_data["login"](phase9_data["admin"])
        r = c.get(reverse("generate_license_key"))
        assert r.status_code == 200
        assert "Generate" in r.content.decode()

    def test_generate_license_key_post(self, phase9_data):
        c = phase9_data["login"](phase9_data["admin"])
        r = c.post(
            reverse("generate_license_key"),
            {
                "school_name": "Test Academy",
                "max_students": 200,
                "max_devices": 2,
                "validity_days": 180,
            },
        )
        assert r.status_code == 200
        html = r.content.decode()
        assert "OC-" in html
        assert "Test Academy" in html

    def test_offline_license_check_valid(self, phase9_data):
        c = phase9_data["login"](phase9_data["admin"])
        r = c.get(reverse("offline_license_check"))
        assert r.status_code == 200
        html = r.content.decode()
        assert "valid" in html.lower()

    def test_offline_license_check_expired(self, phase9_data):
        phase9_data["license"].expires_at = date.today() - timedelta(days=1)
        phase9_data["license"].save()
        c = phase9_data["login"](phase9_data["admin"])
        r = c.get(reverse("offline_license_check"))
        html = r.content.decode()
        assert "expired" in html.lower()

    def test_offline_license_check_no_license(self, phase9_data):
        License.objects.all().delete()
        c = phase9_data["login"](phase9_data["admin"])
        r = c.get(reverse("offline_license_check"))
        html = r.content.decode()
        assert "no license" in html.lower() or "not found" in html.lower()

    def test_license_is_valid_property(self, phase9_data):
        lic = phase9_data["license"]
        assert lic.is_valid is True

    def test_license_expired_not_valid(self, phase9_data):
        lic = phase9_data["license"]
        lic.expires_at = date.today() - timedelta(days=1)
        lic.save()
        assert lic.is_valid is False

    def test_license_days_remaining(self, phase9_data):
        lic = phase9_data["license"]
        assert lic.days_remaining > 0


# ─── SMS Tests ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSMSSystem:
    def test_sms_config_renders(self, phase9_data):
        c = phase9_data["login"](phase9_data["admin"])
        r = c.get(reverse("sms_configuration"))
        assert r.status_code == 200
        html = r.content.decode()
        assert "SMS" in html

    def test_save_sms_config(self, phase9_data):
        c = phase9_data["login"](phase9_data["admin"])
        r = c.post(
            reverse("sms_configuration"),
            {
                "action": "save_config",
                "provider": "twilio",
                "api_key": "AC123",
                "api_secret": "secret123",
                "sender_id": "SCHOOL",
                "daily_limit": "200",
                "is_active": "on",
            },
        )
        assert r.status_code == 302
        phase9_data["sms_config"].refresh_from_db()
        assert phase9_data["sms_config"].provider == "twilio"
        assert phase9_data["sms_config"].api_key == "AC123"
        assert phase9_data["sms_config"].is_active is True

    def test_send_test_sms(self, phase9_data):
        c = phase9_data["login"](phase9_data["admin"])
        r = c.post(
            reverse("sms_configuration"),
            {
                "action": "send_test",
                "test_number": "670000000",
            },
        )
        assert r.status_code == 302
        assert SMSMessage.objects.filter(recipient_number="670000000").exists()

    def test_queue_sms_function(self, phase9_data):
        sms = queue_sms(
            config=phase9_data["sms_config"],
            recipient_number="670000001",
            message="Test message",
            recipient_name="Test User",
        )
        assert sms.status == "queued"
        assert sms.recipient_number == "670000001"

    def test_process_sms_queue_manual_provider(self, phase9_data):
        queue_sms(
            config=phase9_data["sms_config"],
            recipient_number="670000002",
            message="Manual test",
        )
        sent, failed = process_sms_queue()
        assert sent == 1
        assert failed == 0
        sms = SMSMessage.objects.get(recipient_number="670000002")
        assert sms.status == "sent"

    def test_process_sms_queue_twilio_failure(self, phase9_data):
        phase9_data["sms_config"].provider = "twilio"
        phase9_data["sms_config"].api_key = ""
        phase9_data["sms_config"].save()
        sms = queue_sms(
            config=phase9_data["sms_config"],
            recipient_number="670000003",
            message="Twilio test",
        )
        sms.max_retries = 1
        sms.save()
        sent, failed = process_sms_queue()
        assert sent == 0
        assert failed == 1

    def test_sms_daily_limit_check(self, phase9_data):
        config = phase9_data["sms_config"]
        assert config.can_send_today() is True

    def test_sms_history_renders(self, phase9_data):
        queue_sms(
            config=phase9_data["sms_config"],
            recipient_number="670000004",
            message="History test",
        )
        c = phase9_data["login"](phase9_data["admin"])
        r = c.get(reverse("sms_history"))
        assert r.status_code == 200
        assert "670000004" in r.content.decode()

    def test_cancel_sms(self, phase9_data):
        sms = queue_sms(
            config=phase9_data["sms_config"],
            recipient_number="670000005",
            message="Cancel test",
        )
        c = phase9_data["login"](phase9_data["admin"])
        r = c.post(reverse("sms_cancel", args=[sms.pk]))
        assert r.status_code == 302
        sms.refresh_from_db()
        assert sms.status == "cancelled"


# ─── Notification Tests ────────────────────────────────────────────────────


@pytest.mark.django_db
class TestNotifications:
    def test_notifications_list_renders(self, phase9_data):
        Notification.objects.create(
            recipient=phase9_data["admin"],
            notification_type="system",
            title="Test",
            message="Test notification",
        )
        c = phase9_data["login"](phase9_data["admin"])
        r = c.get(reverse("notifications_list"))
        assert r.status_code == 200
        assert "Test" in r.content.decode()

    def test_mark_notification_read(self, phase9_data):
        notif = Notification.objects.create(
            recipient=phase9_data["admin"],
            notification_type="absence",
            title="Absence",
            message="Student absent",
            is_read=False,
        )
        c = phase9_data["login"](phase9_data["admin"])
        r = c.post(reverse("mark_notification_read", args=[notif.pk]))
        assert r.status_code == 302
        notif.refresh_from_db()
        assert notif.is_read is True

    def test_mark_all_read(self, phase9_data):
        for i in range(3):
            Notification.objects.create(
                recipient=phase9_data["admin"],
                notification_type="system",
                title=f"Notif {i}",
                message="msg",
                is_read=False,
            )
        c = phase9_data["login"](phase9_data["admin"])
        r = c.post(reverse("mark_all_read"))
        assert r.status_code == 302
        assert (
            Notification.objects.filter(
                recipient=phase9_data["admin"], is_read=False
            ).count()
            == 0
        )

    def test_unread_count_api(self, phase9_data):
        Notification.objects.create(
            recipient=phase9_data["admin"],
            notification_type="system",
            title="Unread",
            message="msg",
            is_read=False,
        )
        c = phase9_data["login"](phase9_data["admin"])
        r = c.get(reverse("notifications_unread_count"))
        assert r.status_code == 200
        assert json.loads(r.content)["count"] == 1

    def test_send_absence_notification(self, phase9_data):
        send_absence_notification(phase9_data["student"], 5, phase9_data["term"])
        assert Notification.objects.filter(
            recipient=phase9_data["admin"],
            notification_type="absence",
        ).exists()

    def test_send_fee_reminder(self, phase9_data):
        send_fee_reminder(
            phase9_data["student"],
            Decimal(15000),
            str(phase9_data["term"]),
        )
        assert Notification.objects.filter(
            recipient=phase9_data["admin"],
            notification_type="fee_reminder",
        ).exists()

    def test_send_report_ready(self, phase9_data):
        send_report_ready_notification(phase9_data["student"], str(phase9_data["term"]))
        assert Notification.objects.filter(
            recipient=phase9_data["admin"],
            notification_type="report_ready",
        ).exists()

    def test_send_absence_triggers_sms(self, phase9_data):
        send_absence_notification(phase9_data["student"], 3, phase9_data["term"])
        assert SMSMessage.objects.filter(recipient_number="670000001").exists()

    def test_send_fee_reminder_triggers_sms(self, phase9_data):
        send_fee_reminder(
            phase9_data["student"],
            Decimal(10000),
            str(phase9_data["term"]),
        )
        assert SMSMessage.objects.filter(recipient_number="670000001").exists()

    def test_send_report_ready_triggers_sms(self, phase9_data):
        send_report_ready_notification(phase9_data["student"], str(phase9_data["term"]))
        assert SMSMessage.objects.filter(recipient_number="670000001").exists()


# ─── End-to-End Integration Test ───────────────────────────────────────────


@pytest.mark.django_db
class TestPhase9EndToEnd:
    def test_backup_restore_cycle(self, phase9_data):
        create_backup_archive(notes="Pre-change backup", backup_type="database")

        Student.objects.create(
            school=phase9_data["school"],
            first_name="NewStudent",
            sex="M",
            unique_id="111222333",
            date_of_birth=date(2011, 1, 1),
            place_of_birth="Buea",
            guardian_name="G",
            division_of_origin="Meme",
            region_of_origin="South",
        )
        assert Student.objects.filter(first_name="NewStudent").count() == 1

        backup = BackupHistory.objects.first()
        success, msg = restore_backup_archive(backup.pk)
        assert success is True

    def test_license_key_generation_and_validation(self, phase9_data):
        c = phase9_data["login"](phase9_data["admin"])
        r = c.post(
            reverse("generate_license_key"),
            {
                "school_name": "E2E School",
                "max_students": 100,
                "max_devices": 2,
                "validity_days": 30,
            },
        )
        assert r.status_code == 200
        html = r.content.decode()
        assert "OC-" in html

    def test_sms_queue_offline_to_online(self, phase9_data):
        for i in range(5):
            queue_sms(
                config=phase9_data["sms_config"],
                recipient_number=f"67000010{i}",
                message=f"Message {i}",
            )
        assert SMSMessage.objects.filter(status="queued").count() == 5

        sent, failed = process_sms_queue()
        assert sent == 5
        assert failed == 0
        assert SMSMessage.objects.filter(status="sent").count() == 5

    def test_notification_lifecycle(self, phase9_data):
        notif = Notification.objects.create(
            recipient=phase9_data["admin"],
            notification_type="fee_reminder",
            title="Fee Due",
            message="Pay 15000 FCFA",
            is_read=False,
        )

        c = phase9_data["login"](phase9_data["admin"])
        r = c.get(reverse("notifications_unread_count"))
        assert json.loads(r.content)["count"] == 1

        c.post(reverse("mark_notification_read", args=[notif.pk]))
        r = c.get(reverse("notifications_unread_count"))
        assert json.loads(r.content)["count"] == 0
