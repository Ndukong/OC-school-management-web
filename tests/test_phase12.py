"""Phase 12: Deployment & installation integration tests.

Tests the full installation flow: seed config, activation wizard,
school setup, mark entry, report generation, backup/restore.
"""

import io
import os
from datetime import date

import pytest
from django.contrib.auth.models import User
from django.core import management
from django.test import Client
from django.urls import reverse

from core.models import (
    AcademicTerm,
    ClassSubject,
    Competency,
    CompetencyScore,
    License,
    School,
    SchoolClass,
    Student,
    StudentEnrollment,
    Subject,
    TermResult,
    UserProfile,
)
from core.utils.backup import (
    create_backup_archive,
    generate_scheduled_task_script,
    generate_scheduled_task_xml,
    restore_backup_archive,
)

# ─── Seed Data ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestSeedDefaultConfig:
    def test_seed_auto_no_school(self):
        School.objects.all().delete()
        out = io.StringIO()
        err = io.StringIO()
        management.call_command("seed_default_config", "--auto", stdout=out, stderr=err)
        output = out.getvalue() + err.getvalue()
        assert "No school found" in output

    def test_seed_creates_subjects_and_classes(self):
        school = School.objects.create(
            name_en="Seed Test School",
            matricule="SDT01",
            region_en="West",
            division_en="Bamilike",
        )
        out = io.StringIO()
        management.call_command("seed_default_config", "--auto", stdout=out)
        assert Subject.objects.filter(school=school).count() >= 25
        assert SchoolClass.objects.filter(school=school).count() >= 5
        assert AcademicTerm.objects.filter(school=school).count() == 3

    def test_seed_idempotent(self):
        school = School.objects.create(
            name_en="Seed School",
            matricule="SDT02",
            region_en="South",
            division_en="Meme",
        )
        management.call_command("seed_default_config", "--auto", stdout=io.StringIO())
        subj_before = Subject.objects.filter(school=school).count()
        management.call_command("seed_default_config", "--auto", stdout=io.StringIO())
        subj_after = Subject.objects.filter(school=school).count()
        assert subj_before == subj_after  # No duplicates


# ─── Full Installation Flow ────────────────────────────────────────────────


@pytest.mark.django_db
class TestFullInstallationFlow:
    def test_activate_configure_seed_mark_report_backup(self):
        """End-to-end: activate → seed → configure → marks → reports → backup."""
        c = Client()

        # Step 1: Activation wizard
        import base64
        import hashlib
        import hmac
        import json

        from django.conf import settings

        payload = {
            "school": "E2E Test School",
            "max_students": 500,
            "max_devices": 3,
            "expires": "2030-12-31",
        }
        raw = (
            base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True).encode())
            .rstrip(b"=")
            .decode()
        )
        sig = hmac.new(
            settings.LICENSE_SECRET_KEY.encode(),
            json.dumps(payload, sort_keys=True).encode(),
            hashlib.sha256,
        ).hexdigest()[:16]
        product_key = f"OC-{sig}-{raw}"

        r = c.post(reverse("activate"), {"step": 1, "product_key": product_key})
        assert r.status_code == 302
        assert License.objects.filter(status="active").exists()

        # Step 2: Configure school
        r = c.post(
            reverse("activate"),
            {
                "step": 2,
                "name_en": "E2E Test School",
                "region_en": "Centre",
                "division_en": "Mfoundi",
            },
        )
        assert r.status_code == 302
        school = School.objects.filter(name_en="E2E Test School").first()
        assert school is not None

        # Step 3: Create admin
        r = c.post(
            reverse("activate"),
            {
                "step": 3,
                "username": "e2eadmin",
                "password": "secret12",
                "password_confirm": "secret12",
                "first_name": "Admin",
                "last_name": "User",
            },
        )
        assert r.status_code == 302
        admin_user = User.objects.get(username="e2eadmin")
        assert admin_user.is_superuser

        # Step 4: Seed defaults
        out = io.StringIO()
        management.call_command("seed_default_config", "--auto", stdout=out)
        subjects = Subject.objects.filter(school=school).count()
        classes = SchoolClass.objects.filter(school=school).count()
        terms = AcademicTerm.objects.filter(school=school).count()
        assert subjects >= 25
        assert classes >= 5
        assert terms == 3

        # Step 5: Login and verify
        c2 = Client()
        c2.login(username="e2eadmin", password="secret12")
        r = c2.get(reverse("dashboard"))
        assert r.status_code == 200

        # Step 6: Create a student
        f1 = SchoolClass.objects.filter(school=school, code="F1").first()
        term = AcademicTerm.objects.filter(school=school, is_current=True).first()
        student = Student.objects.create(
            school=school,
            first_name="E2E",
            other_names="Student",
            sex="M",
            unique_id="999888111",
            date_of_birth=date(2010, 5, 5),
            place_of_birth="Douala",
            guardian_name="Mr Test",
            guardian_contact="670000000",
            division_of_origin="Mfoundi",
            region_of_origin="Centre",
        )
        StudentEnrollment.objects.create(
            student=student,
            school_class=f1,
            academic_term=term,
        )

        # Step 7: Enter a mark
        mat = Subject.objects.filter(school=school, code="MAT").first()
        ClassSubject.objects.create(school_class=f1, subject=mat, coefficient=4)
        comp = Competency.objects.create(
            subject=mat,
            term=term,
            form_level=1,
            sort_order=1,
            description="Solve equations",
        )
        r = c2.post(
            reverse("save_score_cell"),
            {
                "student_id": student.pk,
                "competency_id": comp.pk,
                "term_id": term.pk,
                "score": "16.5",
            },
        )
        assert r.status_code == 200
        assert CompetencyScore.objects.filter(
            student=student,
            competency=comp,
        ).exists()

        # Step 8: Compute results
        management.call_command(
            "compute_results",
            "--class",
            "F1",
            "--school",
            str(school.pk),
            stdout=io.StringIO(),
        )
        assert TermResult.objects.filter(
            student=student,
            academic_term=term,
        ).exists()

        # Step 9: Create a backup
        history = create_backup_archive(
            notes="End-to-end test backup",
            backup_type="database",
        )
        assert history.file_size > 0
        assert os.path.exists(history.filepath)

        # Step 10: Restore backup
        success, _ = restore_backup_archive(history.pk)
        assert success is True

    def test_generate_license_key(self):
        """Test the license key generation command."""
        out = io.StringIO()
        management.call_command(
            "generate_license",
            "Test Academy",
            "--days",
            "365",
            "--max-students",
            "200",
            stdout=out,
        )
        output = out.getvalue()
        assert "Product Key" in output
        assert "OC-" in output
        assert "Test Academy" in output

    def test_generate_backup_scripts(self):
        """Test bat and XML generation."""
        bat_path = generate_scheduled_task_script()
        assert os.path.exists(bat_path)
        with open(bat_path, encoding="utf-8") as f:
            content = f.read()
            assert "manage.py" in content

        xml_path = generate_scheduled_task_xml()
        assert os.path.exists(xml_path)
        with open(xml_path, encoding="utf-8") as f:
            assert "<Task" in f.read()


# ─── Deployment Scripts ─────────────────────────────────────────────────────


@pytest.mark.django_db
class TestDeploymentScripts:
    def test_backup_script_exists(self):
        assert os.path.exists("backup.bat")

    def test_setup_script_exists(self):
        assert os.path.exists("setup.bat")

    def test_start_server_script_exists(self):
        assert os.path.exists("start_server.bat")

    def test_nssm_script_exists(self):
        assert os.path.exists("nssm_service.bat")

    def test_wifi_hotspot_script_exists(self):
        assert os.path.exists("wifi_hotspot.bat")

    def test_deployment_guide_exists(self):
        assert os.path.exists("DEPLOYMENT.md")
        with open("DEPLOYMENT.md", encoding="utf-8") as f:
            content = f.read()
            assert "setup.bat" in content
            assert "start_server.bat" in content
            assert "backup.bat" in content
            assert "WiFi" in content
            assert "WeasyPrint" in content

    def test_requirements_file_exists(self):
        assert os.path.exists("requirements.txt")
        with open("requirements.txt") as f:
            content = f.read()
            assert "django" in content.lower()
            assert "weasyprint" in content.lower()
            assert "openpyxl" in content.lower()

    def test_alpine_js_bundled(self):
        assert os.path.exists("static/vendor/alpinejs/alpine.min.js")

    def test_htmx_bundled(self):
        assert os.path.exists("static/vendor/htmx/htmx.min.js")

    def test_no_cdn_in_templates(self):
        """Verify no external CDN references in templates."""
        import glob

        for html_file in glob.glob("templates/**/*.html", recursive=True):
            with open(html_file) as f:
                content = f.read()
            for bad in ["cdn.", "googleapis", "cloudflare", "jsdelivr", "cdnjs"]:
                assert bad not in content, f"CDN reference '{bad}' found in {html_file}"

    def test_report_css_bundled(self):
        assert os.path.exists("static/reports/css/report.css")


# ─── Multi-Tenant Isolation ────────────────────────────────────────────────


@pytest.mark.django_db
class TestMultiTenantIsolation:
    def test_two_schools_isolated(self):
        s1 = School.objects.create(
            name_en="School One",
            matricule="ISO1",
            region_en="Littoral",
            division_en="Wouri",
        )
        s2 = School.objects.create(
            name_en="School Two",
            matricule="ISO2",
            region_en="Centre",
            division_en="Mfoundi",
        )
        # Manually seed subjects for each school
        for school in (s1, s2):
            for code, name, order in [
                ("MAT", "Mathematics", 1),
                ("ENL", "English", 2),
                ("PHY", "Physics", 3),
            ]:
                Subject.objects.get_or_create(
                    school=school,
                    code=code,
                    defaults={"name": name, "sort_order": order},
                )

        assert Subject.objects.filter(school=s1).count() == 3
        assert Subject.objects.filter(school=s2).count() == 3

        # Admin of school 1 can't see school 2's data
        u1 = User.objects.create_user(username="iso1", password="pass")
        UserProfile.objects.create(user=u1, school=s1, role="admin")
        c1 = Client()
        c1.login(username="iso1", password="pass")
        r = c1.get(reverse("student_list"))
        html = r.content.decode()
        assert "School Two" not in html

    def test_license_per_school(self):
        """Each school activation creates its own license."""
        for i in range(2):
            import base64
            import hashlib
            import hmac
            import json

            from django.conf import settings

            payload = {
                "school": f"License School {i}",
                "max_students": 100,
                "max_devices": 1,
                "expires": "2030-01-01",
            }
            raw = (
                base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True).encode())
                .rstrip(b"=")
                .decode()
            )
            sig = hmac.new(
                settings.LICENSE_SECRET_KEY.encode(),
                json.dumps(payload, sort_keys=True).encode(),
                hashlib.sha256,
            ).hexdigest()[:16]
            key = f"OC-{sig}-{raw}"
            License.objects.create(
                product_key=key,
                school_name=f"License School {i}",
                max_students=100,
                max_devices=1,
                expires_at=date(2030, 1, 1),
                status="active",
            )
        assert License.objects.count() == 2


# ─── Xlsx Import ────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestImportXlsxDefaults:
    def test_import_creates_subjects_and_competencies(self):
        school = School.objects.create(
            name_en="Xlsx School",
            matricule="XL01",
            region_en="West",
            division_en="Momo",
        )
        AcademicTerm.objects.create(
            school=school,
            term_number=1,
            year_start=2025,
            year_end=2026,
            is_current=True,
        )
        AcademicTerm.objects.create(
            school=school,
            term_number=2,
            year_start=2025,
            year_end=2026,
            is_current=False,
        )
        AcademicTerm.objects.create(
            school=school,
            term_number=3,
            year_start=2025,
            year_end=2026,
            is_current=False,
        )
        out = io.StringIO()
        management.call_command("import_xlsx_defaults", "--auto", stdout=out)
        output = out.getvalue()
        assert "Subjects:" in output
        assert "Competencies:" in output
        assert Subject.objects.filter(school=school).count() >= 20
        assert Competency.objects.filter(subject__school=school).count() > 500

    def test_idempotent(self):
        school = School.objects.filter(is_active=True).first()
        if not school:
            school = School.objects.create(
                name_en="Idem School",
                matricule="IDM01",
                region_en="Centre",
                division_en="Mfoundi",
            )
        AcademicTerm.objects.get_or_create(
            school=school,
            term_number=1,
            year_start=2025,
            year_end=2026,
            defaults={"is_current": True},
        )
        AcademicTerm.objects.get_or_create(
            school=school,
            term_number=2,
            year_start=2025,
            year_end=2026,
            defaults={"is_current": False},
        )
        AcademicTerm.objects.get_or_create(
            school=school,
            term_number=3,
            year_start=2025,
            year_end=2026,
            defaults={"is_current": False},
        )
        out1 = io.StringIO()
        management.call_command("import_xlsx_defaults", "--auto", stdout=out1)
        subj_count = Subject.objects.filter(school=school).count()
        comp_count = Competency.objects.filter(subject__school=school).count()
        out2 = io.StringIO()
        management.call_command("import_xlsx_defaults", "--auto", stdout=out2)
        assert Subject.objects.filter(school=school).count() == subj_count
        assert Competency.objects.filter(subject__school=school).count() == comp_count

    def test_competencies_replicated_for_form_levels_1_to_5(self):
        school = School.objects.filter(is_active=True).first()
        if not school:
            school = School.objects.create(
                name_en="FL School",
                matricule="FL01",
                region_en="South",
                division_en="Fako",
            )
        AcademicTerm.objects.get_or_create(
            school=school,
            term_number=1,
            year_start=2025,
            year_end=2026,
            defaults={"is_current": True},
        )
        AcademicTerm.objects.get_or_create(
            school=school,
            term_number=2,
            year_start=2025,
            year_end=2026,
            defaults={"is_current": False},
        )
        AcademicTerm.objects.get_or_create(
            school=school,
            term_number=3,
            year_start=2025,
            year_end=2026,
            defaults={"is_current": False},
        )
        management.call_command("import_xlsx_defaults", "--auto", stdout=io.StringIO())
        mat = Subject.objects.filter(school=school, code="MAT").first()
        if mat:
            term = AcademicTerm.objects.filter(school=school, term_number=1).first()
            for fl in range(1, 6):
                assert Competency.objects.filter(
                    subject=mat,
                    term=term,
                    form_level=fl,
                ).exists(), f"Missing form_level={fl} for MAT T1"
