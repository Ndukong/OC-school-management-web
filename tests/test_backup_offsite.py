"""Offsite backup uploads and the R2 storage switch."""

import os
import tempfile
from datetime import date
from pathlib import Path

from django.core.files.storage import default_storage
from django.test import TestCase, override_settings

from core.models import School, Student, User
from core.utils.backup import create_backup_archive, upload_archive_offsite


class OffsiteBackupTests(TestCase):
    def setUp(self):
        tmp = tempfile.mkdtemp()
        self.base_dir = Path(tmp)
        self.media_dir = self.base_dir / "media"
        self.media_dir.mkdir(parents=True, exist_ok=True)
        overrides = override_settings(
            BASE_DIR=self.base_dir,
            MEDIA_ROOT=self.media_dir,
            MEDIA_URL="/media/",
        )
        overrides.enable()
        self.addCleanup(overrides.disable)

    def _student(self):
        school = School.objects.create(
            name_en="Backup School",
            matricule="BK-1",
            region_en="SW",
            division_en="Fako",
        )
        user = User.objects.create_user(username="bk_admin", password="pass")
        return school, user

    def test_local_mode_creates_archive_without_upload(self):
        school, user = self._student()
        Student.objects.create(
            school=school,
            first_name="Bee",
            sex="F",
            unique_id="BK0001",
            date_of_birth=date(2010, 2, 2),
            place_of_birth="Buea",
            guardian_name="G",
            division_of_origin="Fako",
            region_of_origin="SW",
        )

        with override_settings(USE_S3=False):
            history = create_backup_archive(user=user, notes="local")

        self.assertTrue(Path(history.filepath).exists())
        self.assertIsNone(upload_archive_offsite(Path(history.filepath)))

    def test_s3_mode_uploads_archive_to_storage(self):
        school, user = self._student()

        with override_settings(USE_S3=True):
            history = create_backup_archive(user=user, notes="offsite")
            stored = default_storage.exists(f"backups/{history.filename}")

        self.assertTrue(stored)
        self.assertIn("offsite copy: backups/", history.notes)

    def test_upload_failure_never_breaks_the_backup(self):
        school, user = self._student()

        with override_settings(USE_S3=True):
            history = create_backup_archive(user=user, notes="x")
            broken = Path(history.filepath) / "does" / "not" / "exist.zip"
            result = upload_archive_offsite(broken)

        self.assertIsNone(result)
        self.assertTrue(Path(history.filepath).exists())


class R2StorageSwitchTests(TestCase):
    def test_settings_declare_storages_and_drop_legacy_setting(self):
        """Guard against the Django 5.1 silent-ignore trap.

        USE_S3 once switched storage via DEFAULT_FILE_STORAGE, which Django
        5.1+ ignores entirely - flipping the flag did nothing. The switch
        must live in STORAGES, and the legacy setting must stay gone.
        """

        import importlib

        os.environ["USE_S3"] = "true"
        try:
            import config.settings as app_settings

            reloaded = importlib.reload(app_settings)
            backend = reloaded.STORAGES["default"]["BACKEND"]
        finally:
            os.environ["USE_S3"] = "false"
            reloaded = importlib.reload(app_settings)

        self.assertIn("s3boto3", backend)
        self.assertEqual(
            reloaded.STORAGES["staticfiles"]["BACKEND"],
            "django.contrib.staticfiles.storage.StaticFilesStorage",
        )
        self.assertFalse(hasattr(reloaded, "DEFAULT_FILE_STORAGE"))
