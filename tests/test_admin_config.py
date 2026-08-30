"""Phase 8: Admin configuration views — full coverage.

Tests:
  - Settings hub renders for admin, 403 for teacher
  - School profile CRUD (including letterhead fields)
  - Terms CRUD (create, set_current, delete)
  - Classes CRUD (create, delete, prevents delete when enrolled)
  - Subjects CRUD (create, delete)
  - Class subjects (add, update coefficient, delete)
  - Competencies (create, filter, delete)
  - Users & teacher links (create user, update role/teacher, reset password)
  - PTA config (rubric heads, sub-heads, dues, fee types)
  - End-to-end: configure an entirely new school from a clean state via the UI
"""

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
    FeeType,
    PTADueConfig,
    PTARubricHead,
    PTARubricSubHead,
    School,
    SchoolClass,
    Student,
    StudentEnrollment,
    Subject,
    Teacher,
    UserProfile,
)


@pytest.fixture
def cfg_data():
    school = School.objects.create(
        name_en="Config School",
        matricule="CFG001",
        region_en="Centre",
        division_en="Mfoundi",
        letterhead_line1_en="REPUBLIC OF CAMEROON",
    )
    sc = SchoolClass.objects.create(
        school=school, name="Form 1", code="F1", form_level=1
    )
    term = AcademicTerm.objects.create(
        school=school, term_number=1, year_start=2025, year_end=2026, is_current=True
    )
    subject = Subject.objects.create(school=school, name="Mathematics", code="MAT")
    teacher = Teacher.objects.create(
        school=school, first_name="Jean", last_name="Dupont", teacher_code="T001"
    )

    user = User.objects.create_user(
        username="cfgadmin", password="pass", is_staff=True, is_superuser=True
    )
    UserProfile.objects.create(user=user, school=school, role="admin")

    teacher_user = User.objects.create_user(username="teacher1", password="pass")
    UserProfile.objects.create(user=teacher_user, school=school, role="teacher")

    def login(u):
        c = Client()
        c.login(username=u.username, password="pass")
        return c

    return {
        "school": school,
        "sc": sc,
        "term": term,
        "subject": subject,
        "teacher": teacher,
        "user": user,
        "teacher_user": teacher_user,
        "login": login,
    }


@pytest.mark.django_db
class TestSettingsHub:
    def test_admin_renders_hub(self, cfg_data):
        c = cfg_data["login"](cfg_data["user"])
        r = c.get(reverse("settings"))
        assert r.status_code == 200
        html = r.content.decode()
        assert "School Configuration" in html
        assert "School Profile" in html
        assert "Academic Terms" in html

    def test_teacher_forbidden(self, cfg_data):
        c = cfg_data["login"](cfg_data["teacher_user"])
        r = c.get(reverse("settings"))
        assert r.status_code == 403

    def test_unauthenticated_redirects(self):
        c = Client()
        r = c.get(reverse("settings"))
        assert r.status_code == 302


@pytest.mark.django_db
class TestSchoolProfile:
    def test_school_profile_renders(self, cfg_data):
        c = cfg_data["login"](cfg_data["user"])
        r = c.get(reverse("school_profile"))
        assert r.status_code == 200
        html = r.content.decode()
        assert "Config School" in html
        assert "REPUBLIC OF CAMEROON" in html
        assert "letterhead_line3_en" in html

    def test_school_profile_update_letterhead(self, cfg_data):
        c = cfg_data["login"](cfg_data["user"])
        data = {
            "name_en": "Updated School",
            "matricule": "CFG001",
            "region_en": "Centre",
            "division_en": "Mfoundi",
            "letterhead_line3_en": "EXTRA EN LINE",
            "letterhead_line3_fr": "LIGNE FR SUPPL",
        }
        r = c.post(reverse("school_profile"), data)
        assert r.status_code == 302
        cfg_data["school"].refresh_from_db()
        assert cfg_data["school"].name_en == "Updated School"
        assert cfg_data["school"].letterhead_line3_en == "EXTRA EN LINE"
        assert cfg_data["school"].letterhead_line3_fr == "LIGNE FR SUPPL"

    def test_letterhead_line1_line2_not_editable(self, cfg_data):
        c = cfg_data["login"](cfg_data["user"])
        r = c.get(reverse("school_profile"))
        html = r.content.decode()
        assert 'name="letterhead_line1_en"' not in html
        assert 'name="letterhead_line2_en"' not in html
        assert "REPUBLIC OF CAMEROON" in html

    def test_school_profile_preview_includes_letterhead(self, cfg_data):
        c = cfg_data["login"](cfg_data["user"])
        r = c.get(reverse("school_profile"))
        html = r.content.decode()
        assert "REPUBLIC OF CAMEROON" in html

    def test_teacher_cannot_access(self, cfg_data):
        c = cfg_data["login"](cfg_data["teacher_user"])
        r = c.get(reverse("school_profile"))
        assert r.status_code == 403


@pytest.mark.django_db
class TestTermsManage:
    def test_terms_list_renders(self, cfg_data):
        c = cfg_data["login"](cfg_data["user"])
        r = c.get(reverse("terms_manage"))
        assert r.status_code == 200
        html = r.content.decode()
        assert "First Term" in html

    def test_create_term(self, cfg_data):
        c = cfg_data["login"](cfg_data["user"])
        r = c.post(
            reverse("terms_manage"),
            {
                "action": "create",
                "term_number": 2,
                "year_start": 2025,
                "year_end": 2026,
                "is_current": False,
            },
        )
        assert r.status_code == 302
        assert (
            AcademicTerm.objects.filter(
                school=cfg_data["school"], term_number=2
            ).count()
            == 1
        )

    def test_set_current_term(self, cfg_data):
        t2 = AcademicTerm.objects.create(
            school=cfg_data["school"],
            term_number=2,
            year_start=2025,
            year_end=2026,
            is_current=False,
        )
        c = cfg_data["login"](cfg_data["user"])
        r = c.post(
            reverse("terms_manage"),
            {
                "action": "set_current",
                "term_id": t2.pk,
            },
        )
        assert r.status_code == 302
        cfg_data["term"].refresh_from_db()
        t2.refresh_from_db()
        assert cfg_data["term"].is_current is False
        assert t2.is_current is True

    def test_delete_term(self, cfg_data):
        t2 = AcademicTerm.objects.create(
            school=cfg_data["school"],
            term_number=3,
            year_start=2025,
            year_end=2026,
        )
        c = cfg_data["login"](cfg_data["user"])
        r = c.post(
            reverse("terms_manage"),
            {
                "action": "delete",
                "term_id": t2.pk,
            },
        )
        assert r.status_code == 302
        assert AcademicTerm.objects.filter(pk=t2.pk).count() == 0


@pytest.mark.django_db
class TestClassesManage:
    def test_classes_list_renders(self, cfg_data):
        c = cfg_data["login"](cfg_data["user"])
        r = c.get(reverse("classes_manage"))
        assert r.status_code == 200
        assert "Form 1" in r.content.decode()

    def test_create_class(self, cfg_data):
        c = cfg_data["login"](cfg_data["user"])
        r = c.post(
            reverse("classes_manage"),
            {
                "action": "create",
                "name": "Form 2",
                "code": "F2",
                "stream": "A",
                "cycle": "first",
                "form_level": 2,
                "promotion_mark": 10,
                "sort_order": 2,
            },
        )
        assert r.status_code == 302
        assert SchoolClass.objects.filter(
            school=cfg_data["school"], code="F2", stream="A"
        ).exists()

    def test_delete_class(self, cfg_data):
        sc = SchoolClass.objects.create(
            school=cfg_data["school"], name="Temp", code="TMP"
        )
        c = cfg_data["login"](cfg_data["user"])
        r = c.post(
            reverse("classes_manage"),
            {
                "action": "delete",
                "class_id": sc.pk,
            },
        )
        assert r.status_code == 302
        assert not SchoolClass.objects.filter(pk=sc.pk).exists()

    def test_cannot_delete_enrolled_class(self, cfg_data):
        Student.objects.create(
            school=cfg_data["school"],
            first_name="A",
            sex="M",
            unique_id="111222333",
            date_of_birth=date(2010, 1, 1),
            place_of_birth="B",
            guardian_name="G",
            division_of_origin="F",
            region_of_origin="SW",
        )
        s = Student.objects.first()
        StudentEnrollment.objects.create(
            student=s, school_class=cfg_data["sc"], academic_term=cfg_data["term"]
        )
        c = cfg_data["login"](cfg_data["user"])
        r = c.post(
            reverse("classes_manage"),
            {
                "action": "delete",
                "class_id": cfg_data["sc"].pk,
            },
        )
        assert r.status_code == 302
        assert SchoolClass.objects.filter(pk=cfg_data["sc"].pk).exists()

    def test_duplicate_class_code_returns_302_not_500(self, cfg_data):
        """Regression: duplicate (code, stream) must not raise IntegrityError."""
        c = cfg_data["login"](cfg_data["user"])
        r = c.post(
            reverse("classes_manage"),
            {
                "action": "create",
                "name": "Duplicate",
                "code": "F1",  # already exists
                "stream": "",
                "cycle": "first",
                "form_level": 1,
                "promotion_mark": 10,
                "sort_order": 9,
            },
        )
        assert r.status_code == 302
        count = SchoolClass.objects.filter(school=cfg_data["school"], code="F1").count()
        assert count == 1  # no duplicate inserted

    def test_duplicate_class_same_code_diff_stream_allowed(self, cfg_data):
        """Same code with different stream should still be allowed."""
        c = cfg_data["login"](cfg_data["user"])
        r = c.post(
            reverse("classes_manage"),
            {
                "action": "create",
                "name": "Form 1 B",
                "code": "F1",
                "stream": "B",
                "cycle": "first",
                "form_level": 1,
                "promotion_mark": 10,
                "sort_order": 9,
            },
        )
        assert r.status_code == 302
        assert SchoolClass.objects.filter(
            school=cfg_data["school"], code="F1", stream="B"
        ).exists()

    def test_code_uppercased_on_create(self, cfg_data):
        c = cfg_data["login"](cfg_data["user"])
        r = c.post(
            reverse("classes_manage"),
            {
                "action": "create",
                "name": "New Class",
                "code": "n3",
                "stream": "",
                "cycle": "first",
                "form_level": 3,
                "promotion_mark": 10,
                "sort_order": 9,
            },
        )
        assert r.status_code == 302
        assert SchoolClass.objects.filter(school=cfg_data["school"], code="N3").exists()


@pytest.mark.django_db
class TestSubjectsManage:
    def test_subjects_list_renders(self, cfg_data):
        c = cfg_data["login"](cfg_data["user"])
        r = c.get(reverse("subjects_manage"))
        assert r.status_code == 200
        assert "Mathematics" in r.content.decode()

    def test_create_subject(self, cfg_data):
        c = cfg_data["login"](cfg_data["user"])
        r = c.post(
            reverse("subjects_manage"),
            {
                "action": "create",
                "name": "English Language",
                "code": "ENL",
                "sort_order": 1,
            },
        )
        assert r.status_code == 302
        assert Subject.objects.filter(school=cfg_data["school"], code="ENL").exists()

    def test_delete_subject(self, cfg_data):
        s = Subject.objects.create(school=cfg_data["school"], name="Temp", code="TMP")
        c = cfg_data["login"](cfg_data["user"])
        r = c.post(
            reverse("subjects_manage"),
            {
                "action": "delete",
                "subject_id": s.pk,
            },
        )
        assert r.status_code == 302
        assert not Subject.objects.filter(pk=s.pk).exists()

    def test_duplicate_subject_code_returns_302_not_500(self, cfg_data):
        """Regression: duplicate subject code must not raise IntegrityError."""
        c = cfg_data["login"](cfg_data["user"])
        r = c.post(
            reverse("subjects_manage"),
            {
                "action": "create",
                "name": "Duplicate Math",
                "code": "MAT",  # already exists
                "sort_order": 9,
            },
        )
        assert r.status_code == 302
        assert (
            Subject.objects.filter(school=cfg_data["school"], code="MAT").count() == 1
        )

    def test_subject_code_uppercased_on_create(self, cfg_data):
        c = cfg_data["login"](cfg_data["user"])
        r = c.post(
            reverse("subjects_manage"),
            {
                "action": "create",
                "name": "Physics",
                "code": "phy",
                "sort_order": 9,
            },
        )
        assert r.status_code == 302
        assert Subject.objects.filter(school=cfg_data["school"], code="PHY").exists()


@pytest.mark.django_db
class TestClassSubjectsManage:
    def test_add_subject_to_class(self, cfg_data):
        c = cfg_data["login"](cfg_data["user"])
        r = c.post(
            reverse("class_subjects_manage", args=[cfg_data["sc"].pk]),
            {
                "action": "add",
                "subject": cfg_data["subject"].pk,
                "coefficient": 4,
                "sort_order": 1,
            },
        )
        assert r.status_code == 302
        cs = ClassSubject.objects.get(
            school_class=cfg_data["sc"], subject=cfg_data["subject"]
        )
        assert cs.coefficient == 4

    def test_update_coefficient(self, cfg_data):
        cs = ClassSubject.objects.create(
            school_class=cfg_data["sc"],
            subject=cfg_data["subject"],
            coefficient=2,
        )
        c = cfg_data["login"](cfg_data["user"])
        r = c.post(
            reverse("class_subjects_manage", args=[cfg_data["sc"].pk]),
            {
                "action": "update",
                "cs_id": cs.pk,
                "coefficient": 6,
            },
        )
        assert r.status_code == 302
        cs.refresh_from_db()
        assert cs.coefficient == 6

    def test_delete_class_subject(self, cfg_data):
        cs = ClassSubject.objects.create(
            school_class=cfg_data["sc"],
            subject=cfg_data["subject"],
            coefficient=3,
        )
        c = cfg_data["login"](cfg_data["user"])
        r = c.post(
            reverse("class_subjects_manage", args=[cfg_data["sc"].pk]),
            {
                "action": "delete",
                "cs_id": cs.pk,
            },
        )
        assert r.status_code == 302
        assert not ClassSubject.objects.filter(pk=cs.pk).exists()

    def test_class_subjects_index_renders(self, cfg_data):
        c = cfg_data["login"](cfg_data["user"])
        r = c.get(reverse("class_subjects_all"))
        assert r.status_code == 200
        assert "Form 1" in r.content.decode()


@pytest.mark.django_db
class TestCompetenciesManage:
    def test_competencies_list_renders(self, cfg_data):
        c = cfg_data["login"](cfg_data["user"])
        r = c.get(reverse("competencies_manage"))
        assert r.status_code == 200

    def test_create_competency(self, cfg_data):
        c = cfg_data["login"](cfg_data["user"])
        r = c.post(
            reverse("competencies_manage"),
            {
                "action": "create",
                "subject": cfg_data["subject"].pk,
                "term": cfg_data["term"].pk,
                "form_level": 1,
                "description": "Solve quadratic equations",
                "sort_order": 1,
            },
        )
        assert r.status_code == 302
        assert Competency.objects.filter(
            subject=cfg_data["subject"],
            term=cfg_data["term"],
            description="Solve quadratic equations",
        ).exists()

    def test_filter_competencies(self, cfg_data):
        Competency.objects.create(
            subject=cfg_data["subject"],
            term=cfg_data["term"],
            form_level=1,
            description="C1",
            sort_order=1,
        )
        c = cfg_data["login"](cfg_data["user"])
        r = c.get(
            reverse("competencies_manage"),
            {
                "subject_id": cfg_data["subject"].pk,
                "term_id": cfg_data["term"].pk,
                "form_level": 1,
            },
        )
        assert r.status_code == 200
        assert "C1" in r.content.decode()

    def test_delete_competency(self, cfg_data):
        comp = Competency.objects.create(
            subject=cfg_data["subject"],
            term=cfg_data["term"],
            form_level=1,
            description="To delete",
            sort_order=1,
        )
        c = cfg_data["login"](cfg_data["user"])
        r = c.post(
            reverse("competencies_manage"),
            {
                "action": "delete",
                "competency_id": comp.pk,
            },
        )
        assert r.status_code == 302
        assert not Competency.objects.filter(pk=comp.pk).exists()


@pytest.mark.django_db
class TestUsersManage:
    def test_users_list_renders(self, cfg_data):
        c = cfg_data["login"](cfg_data["user"])
        r = c.get(reverse("users_manage"))
        assert r.status_code == 200
        assert "cfgadmin" in r.content.decode()

    def test_create_user_with_teacher_link(self, cfg_data):
        c = cfg_data["login"](cfg_data["user"])
        r = c.post(
            reverse("users_manage"),
            {
                "action": "create",
                "username": "newteacher",
                "password": "secure123",
                "password_confirm": "secure123",
                "first_name": "Marie",
                "last_name": "Kamga",
                "role": "class_master",
                "teacher": cfg_data["teacher"].pk,
            },
        )
        assert r.status_code == 302
        new_user = User.objects.get(username="newteacher")
        profile = UserProfile.objects.get(user=new_user)
        assert profile.role == "class_master"
        assert profile.teacher == cfg_data["teacher"]
        assert profile.school == cfg_data["school"]

    def test_create_user_no_password_match(self, cfg_data):
        c = cfg_data["login"](cfg_data["user"])
        r = c.post(
            reverse("users_manage"),
            {
                "action": "create",
                "username": "failuser",
                "password": "abc",
                "password_confirm": "xyz",
                "role": "teacher",
            },
        )
        assert r.status_code == 302
        assert not User.objects.filter(username="failuser").exists()

    def test_update_user_role(self, cfg_data):
        c = cfg_data["login"](cfg_data["user"])
        profile = cfg_data["teacher_user"].profile
        r = c.post(
            reverse("users_manage"),
            {
                "action": "update",
                "profile_id": profile.pk,
                "role": "class_master",
                "phone": "650000000",
                "first_name": "Updated",
                "last_name": "Name",
                "email": "u@test.com",
            },
        )
        assert r.status_code == 302
        profile.refresh_from_db()
        cfg_data["teacher_user"].refresh_from_db()
        assert profile.role == "class_master"
        assert profile.phone == "650000000"
        assert cfg_data["teacher_user"].first_name == "Updated"

    def test_reset_password(self, cfg_data):
        c = cfg_data["login"](cfg_data["user"])
        profile = cfg_data["teacher_user"].profile
        r = c.post(
            reverse("users_manage"),
            {
                "action": "reset_password",
                "profile_id": profile.pk,
                "password": "newpass123",
            },
        )
        assert r.status_code == 302
        c2 = Client()
        assert c2.login(
            username=cfg_data["teacher_user"].username, password="newpass123"
        )

    def test_duplicate_username_rejected(self, cfg_data):
        c = cfg_data["login"](cfg_data["user"])
        r = c.post(
            reverse("users_manage"),
            {
                "action": "create",
                "username": "cfgadmin",
                "password": "pass1234",
                "password_confirm": "pass1234",
                "role": "teacher",
            },
        )
        assert r.status_code == 302
        assert User.objects.filter(username="cfgadmin").count() == 1


@pytest.mark.django_db
class TestPTAConfig:
    def test_pta_config_renders(self, cfg_data):
        c = cfg_data["login"](cfg_data["user"])
        r = c.get(reverse("pta_config"))
        assert r.status_code == 200
        html = r.content.decode()
        assert "PTA Dues per Class" in html
        assert "Fee Types" in html

    def test_add_rubric_head(self, cfg_data):
        c = cfg_data["login"](cfg_data["user"])
        r = c.post(
            reverse("pta_config"),
            {
                "action": "add_head",
                "name": "Infrastructure",
                "code": "INFRA",
                "sort_order": 1,
            },
        )
        assert r.status_code == 302
        assert PTARubricHead.objects.filter(
            school=cfg_data["school"], name="Infrastructure"
        ).exists()

    def test_add_rubric_subhead(self, cfg_data):
        head = PTARubricHead.objects.create(
            school=cfg_data["school"], name="Admin", code="ADM", sort_order=1
        )
        c = cfg_data["login"](cfg_data["user"])
        r = c.post(
            reverse("pta_config"),
            {
                "action": "add_subhead",
                "rubric_head": head.pk,
                "name": "Office Supplies",
                "code": "SUPP",
            },
        )
        assert r.status_code == 302
        assert PTARubricSubHead.objects.filter(
            rubric_head=head, name="Office Supplies"
        ).exists()

    def test_save_pta_dues(self, cfg_data):
        c = cfg_data["login"](cfg_data["user"])
        sc = cfg_data["sc"]
        r = c.post(
            reverse("pta_config"),
            {
                "action": "save_dues",
                f"due_{sc.pk}": "5000",
            },
        )
        assert r.status_code == 302
        due = PTADueConfig.objects.get(school=cfg_data["school"], school_class=sc)
        assert due.amount == Decimal(5000)

    def test_add_fee_type(self, cfg_data):
        c = cfg_data["login"](cfg_data["user"])
        r = c.post(
            reverse("pta_config"),
            {
                "action": "add_feetype",
                "name": "PTA Registration",
                "category": "PTA",
            },
        )
        assert r.status_code == 302
        assert FeeType.objects.filter(
            school=cfg_data["school"], name="PTA Registration"
        ).exists()

    def test_delete_fee_type(self, cfg_data):
        ft = FeeType.objects.create(
            school=cfg_data["school"], name="Temp Fee", category="state"
        )
        c = cfg_data["login"](cfg_data["user"])
        r = c.post(
            reverse("pta_config"),
            {
                "action": "delete_feetype",
                "feetype_id": ft.pk,
            },
        )
        assert r.status_code == 302
        assert not FeeType.objects.filter(pk=ft.pk).exists()


@pytest.mark.django_db
class TestEndToEndNewSchool:
    """A brand-new school configured entirely through the UI — no Django Admin."""

    def test_full_school_setup_via_ui(self):
        c = Client()

        # ── Step 1: Activate license ─────────────────────────────────────
        import base64
        import hashlib
        import hmac
        import json

        from django.conf import settings as django_settings

        payload = {
            "school": "New School E2E",
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
            django_settings.LICENSE_SECRET_KEY.encode(),
            json.dumps(payload, sort_keys=True).encode(),
            hashlib.sha256,
        ).hexdigest()[:16]
        product_key = f"OC-{sig}-{raw}"

        r = c.post(
            reverse("activate"),
            {
                "step": 1,
                "product_key": product_key,
            },
        )
        assert r.status_code == 302

        # ── Step 2: Setup school ─────────────────────────────────────────
        r = c.post(
            reverse("activate"),
            {
                "step": 2,
                "name_en": "New School E2E",
                "region_en": "Littoral",
                "division_en": "Wouri",
                "phone": "233000000",
                "motto_en": "Knowledge is Power",
            },
        )
        assert r.status_code == 302
        school = School.objects.get(name_en="New School E2E")
        assert school.region_en == "Littoral"

        # ── Step 3: Setup admin ──────────────────────────────────────────
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
        assert not admin_user.is_superuser

        # ── Login as the new admin ───────────────────────────────────────
        c2 = Client()
        c2.login(username="e2eadmin", password="secret12")

        # ── School profile: add letterhead + matricule fix ───────────────
        r = c2.post(
            reverse("school_profile"),
            {
                "name_en": "New School E2E",
                "matricule": "E2E-001",
                "region_en": "Littoral",
                "division_en": "Wouri",
                "letterhead_line3_en": "EXTRA EN",
                "letterhead_line3_fr": "LIGNE FR",
            },
        )
        assert r.status_code == 302
        school.refresh_from_db()
        assert school.matricule == "E2E-001"
        assert school.letterhead_line1_en == "REPUBLIC OF CAMEROON"

        # ── Create academic term (next academic year — wizard seeded 2025/2026) ──
        r = c2.post(
            reverse("terms_manage"),
            {
                "action": "create",
                "term_number": 1,
                "year_start": 2026,
                "year_end": 2027,
                "is_current": True,
            },
        )
        assert r.status_code == 302
        term = AcademicTerm.objects.get(school=school, year_start=2026, term_number=1)
        assert term.is_current

        # ── Create classes (wizard seeded F1-F5/LS/US, so use fresh codes) ────
        for code, name, fl in [("XA", "Form X", 1), ("XB", "Form Y", 2)]:
            r = c2.post(
                reverse("classes_manage"),
                {
                    "action": "create",
                    "name": name,
                    "code": code,
                    "stream": "",
                    "cycle": "first",
                    "form_level": fl,
                    "promotion_mark": 10,
                    "dismissal_mark": 8,
                    "sort_order": fl,
                },
            )
            assert r.status_code == 302
        assert SchoolClass.objects.filter(school=school).count() == 9
        f1 = SchoolClass.objects.get(school=school, code="XA")

        # ── Create subjects (wizard seeded 30, so use fresh codes) ────────
        for code, name in [
            ("XP1", "X Programming One"),
            ("XP2", "X Programming Two"),
            ("XP3", "X Science"),
        ]:
            r = c2.post(
                reverse("subjects_manage"),
                {
                    "action": "create",
                    "name": name,
                    "code": code,
                    "sort_order": 1,
                },
            )
            assert r.status_code == 302
        assert Subject.objects.filter(school=school).count() == 33
        mat = Subject.objects.get(school=school, code="XP1")

        # ── Assign subject to class with coefficient ─────────────────────
        r = c2.post(
            reverse("class_subjects_manage", args=[f1.pk]),
            {
                "action": "add",
                "subject": mat.pk,
                "coefficient": 4,
                "sort_order": 1,
            },
        )
        assert r.status_code == 302
        cs = ClassSubject.objects.get(school_class=f1, subject=mat)
        assert cs.coefficient == 4

        # ── Add competency ───────────────────────────────────────────────
        r = c2.post(
            reverse("competencies_manage"),
            {
                "action": "create",
                "subject": mat.pk,
                "term": term.pk,
                "form_level": 1,
                "description": "Solve first-degree equations",
                "sort_order": 1,
            },
        )
        assert r.status_code == 302
        assert Competency.objects.filter(subject=mat, term=term).exists()

        # ── Create teacher then user + link ──────────────────────────────
        teacher = Teacher.objects.create(
            school=school, first_name="Tina", last_name="Ateh", teacher_code="T01"
        )
        r = c2.post(
            reverse("users_manage"),
            {
                "action": "create",
                "username": "tinaa",
                "password": "teach12",
                "password_confirm": "teach12",
                "first_name": "Tina",
                "last_name": "Ateh",
                "role": "teacher",
                "teacher": teacher.pk,
            },
        )
        assert r.status_code == 302
        tina = User.objects.get(username="tinaa")
        profile = UserProfile.objects.get(user=tina)
        assert profile.teacher == teacher

        # ── PTA: head, subhead, dues, fee type ──────────────────────────
        r = c2.post(
            reverse("pta_config"),
            {
                "action": "add_head",
                "name": "Infrastructure",
                "code": "INFRA",
                "sort_order": 1,
            },
        )
        assert r.status_code == 302
        head = PTARubricHead.objects.get(school=school, name="Infrastructure")

        r = c2.post(
            reverse("pta_config"),
            {
                "action": "add_subhead",
                "rubric_head": head.pk,
                "name": "Classrooms",
                "code": "CR",
            },
        )
        assert r.status_code == 302

        r = c2.post(
            reverse("pta_config"),
            {
                "action": "save_dues",
                f"due_{f1.pk}": "15000",
            },
        )
        assert r.status_code == 302
        due = PTADueConfig.objects.get(school=school, school_class=f1)
        assert due.amount == Decimal(15000)

        r = c2.post(
            reverse("pta_config"),
            {
                "action": "add_feetype",
                "name": "PTA Term Dues",
                "category": "PTA",
            },
        )
        assert r.status_code == 302
        assert FeeType.objects.filter(school=school, name="PTA Term Dues").exists()

        # ── Verify all school-scoped ─────────────────────────────────────
        assert AcademicTerm.objects.filter(school=school).count() == 4
        assert SchoolClass.objects.filter(school=school).count() == 9
        assert Subject.objects.filter(school=school).count() == 33
        assert ClassSubject.objects.filter(school_class__school=school).count() == 1
        assert Competency.objects.filter(subject__school=school).count() == 1
        assert UserProfile.objects.filter(school=school).count() == 2
        assert PTADueConfig.objects.filter(school=school).count() == 1
        assert FeeType.objects.filter(school=school).count() == 1
        assert PTARubricHead.objects.filter(school=school).count() == 1
        assert PTARubricSubHead.objects.filter(rubric_head__school=school).count() == 1

        # ── Settings hub loads ───────────────────────────────────────────
        r = c2.get(reverse("settings"))
        assert r.status_code == 200
        html = r.content.decode()
        assert "New School E2E" in html
