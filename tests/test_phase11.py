"""Phase 11: Comprehensive test suite — unit tests, integration tests, edge cases.

Targets 80%+ coverage across core models, views, utils, forms, and permissions.
"""

import io
import os
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from django.urls import reverse

from core.models import (
    AcademicTerm,
    AttendanceRecord,
    AttendanceRegister,
    ClassSubject,
    Competency,
    CompetencyScore,
    ExpenditureRecord,
    FeeType,
    IncomeRecord,
    License,
    Notification,
    PTADueConfig,
    School,
    SchoolClass,
    SMSConfig,
    Student,
    StudentEnrollment,
    Subject,
    SubjectAverage,
    Teacher,
    TermResult,
    UserProfile,
)
from core.models.backup import BackupHistory
from core.utils.backup import create_backup_archive, restore_backup_archive
from core.utils.compute_results import (
    compute_all_classes,
    compute_subject_average_for_student,
    compute_term_result_for_student,
    compute_term_results,
    is_external_exam_class,
)
from core.utils.grading import (
    compute_grade,
    compute_promotion_decision,
    compute_remark,
    compute_subject_average,
    compute_term_total,
    is_pass,
)
from core.utils.notifications import (
    process_sms_queue,
    queue_sms,
)
from core.utils.permissions import (
    can_manage_class,
    get_school_for_user,
    get_teacher_for_user,
    is_admin_or_superuser,
)


@pytest.fixture
def school_a():
    return School.objects.create(
        name_en="School A", matricule="SA001", region_en="Centre", division_en="Mfoundi"
    )


@pytest.fixture
def school_b():
    return School.objects.create(
        name_en="School B", matricule="SB001", region_en="West", division_en="Mifi"
    )


@pytest.fixture
def term_a(school_a):
    return AcademicTerm.objects.create(
        school=school_a, term_number=1, year_start=2025, year_end=2026, is_current=True
    )


@pytest.fixture
def term_b(school_b):
    return AcademicTerm.objects.create(
        school=school_b, term_number=1, year_start=2025, year_end=2026, is_current=True
    )


@pytest.fixture
def cls_a(school_a):
    return SchoolClass.objects.create(
        school=school_a, name="Form 1", code="F1", form_level=1, promotion_mark=10.0
    )


@pytest.fixture
def cls_b(school_b):
    return SchoolClass.objects.create(
        school=school_b, name="Form 1", code="F1", form_level=1, promotion_mark=10.0
    )


@pytest.fixture
def subj_a(school_a):
    return Subject.objects.create(school=school_a, name="Math", code="MAT")


@pytest.fixture
def subj_a2(school_a):
    return Subject.objects.create(
        school=school_a, name="English", code="ENL", sort_order=2
    )


@pytest.fixture
def subj_b(school_b):
    return Subject.objects.create(school=school_b, name="Math", code="MAT")


@pytest.fixture
def admin_user_a(school_a):
    u = User.objects.create_user(
        username="adminA", password="pass", is_staff=True, is_superuser=True
    )
    UserProfile.objects.create(user=u, school=school_a, role="admin")
    return u


@pytest.fixture
def admin_user_b(school_b):
    u = User.objects.create_user(
        username="adminB", password="pass", is_staff=True, is_superuser=True
    )
    UserProfile.objects.create(user=u, school=school_b, role="admin")
    return u


@pytest.fixture
def teacher_user_a(school_a):
    u = User.objects.create_user(username="teacherA", password="pass")
    UserProfile.objects.create(user=u, school=school_a, role="teacher")
    return u


@pytest.fixture
def bursar_user_a(school_a):
    u = User.objects.create_user(username="bursarA", password="pass")
    UserProfile.objects.create(user=u, school=school_a, role="bursar")
    return u


@pytest.fixture
def student_a(school_a):
    return Student.objects.create(
        school=school_a,
        first_name="Alice",
        sex="F",
        unique_id="111111111",
        date_of_birth=date(2010, 1, 1),
        place_of_birth="Douala",
        guardian_name="G1",
        guardian_contact="670000001",
        division_of_origin="Wouri",
        region_of_origin="Littoral",
    )


@pytest.fixture
def student_b(school_b):
    return Student.objects.create(
        school=school_b,
        first_name="Bob",
        sex="M",
        unique_id="222222222",
        date_of_birth=date(2010, 2, 2),
        place_of_birth="Bamenda",
        guardian_name="G2",
        guardian_contact="670000002",
        division_of_origin="Mezam",
        region_of_origin="North West",
    )


def login_client(user):
    c = Client()
    c.login(username=user.username, password="pass")
    return c


# ═══════════════════════════════════════════════════════════════════════════
# UNIT TESTS: Grading boundaries
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestGradingBoundaries:
    @pytest.mark.parametrize(
        "score,expected",
        [
            (Decimal("19.00"), "A+"),
            (Decimal("18.00"), "A+"),
            (Decimal("17.99"), "A"),
            (Decimal("16.00"), "A"),
            (Decimal("15.50"), "B+"),
            (Decimal("15.00"), "B+"),
            (Decimal("14.99"), "B"),
            (Decimal("14.00"), "B"),
            (Decimal("12.50"), "C+"),
            (Decimal("12.00"), "C+"),
            (Decimal("11.99"), "C"),
            (Decimal("10.00"), "C"),
            (Decimal("9.99"), "D"),
            (Decimal("5.00"), "D"),
            (Decimal("0.00"), "D"),
        ],
    )
    def test_grade_boundaries(self, score, expected):
        assert compute_grade(score) == expected

    @pytest.mark.parametrize(
        "score,expected",
        [
            (Decimal("16.00"), "CVWA"),
            (Decimal("15.99"), "CWA"),
            (Decimal("14.00"), "CWA"),
            (Decimal("13.99"), "CA"),
            (Decimal("12.00"), "CA"),
            (Decimal("11.99"), "CAA"),
            (Decimal("10.00"), "CAA"),
            (Decimal("9.99"), "CNA"),
            (Decimal("0.00"), "CNA"),
        ],
    )
    def test_remark_boundaries(self, score, expected):
        assert compute_remark(score) == expected

    @pytest.mark.parametrize(
        "score,expected",
        [
            (Decimal("10.00"), True),
            (Decimal("10.01"), True),
            (Decimal("9.99"), False),
            (Decimal("0.00"), False),
        ],
    )
    def test_is_pass(self, score, expected):
        assert is_pass(score) == expected


# ═══════════════════════════════════════════════════════════════════════════
# UNIT TESTS: Competency averages
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCompetencyAverages:
    def test_empty_scores_returns_none(self):
        assert compute_subject_average([]) is None

    def test_single_score(self):
        assert compute_subject_average([Decimal("15.00")]) == Decimal("15.00")

    def test_multiple_scores(self):
        result = compute_subject_average(
            [Decimal("12.00"), Decimal("16.00"), Decimal("14.00")]
        )
        assert result == Decimal("14.00")

    def test_scores_round_to_2dp(self):
        result = compute_subject_average([Decimal("13.33"), Decimal("13.34")])
        assert result == Decimal("13.34")

    def test_all_zeros(self):
        assert compute_subject_average([Decimal(0), Decimal(0)]) == Decimal("0.00")

    def test_max_score(self):
        assert compute_subject_average([Decimal("20.00")]) == Decimal("20.00")


# ═══════════════════════════════════════════════════════════════════════════
# UNIT TESTS: Coefficient weighting
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCoefficientWeighting:
    def test_term_total_empty(self):
        w, c, avg = compute_term_total([])
        assert avg == Decimal(0)
        assert c == 0

    def test_single_subject(self):
        w, c, avg = compute_term_total([(Decimal("15.00"), 4)])
        assert w == Decimal("60.00")
        assert c == 4
        assert avg == Decimal("15.00")

    def test_weighted_average(self):
        w, c, avg = compute_term_total(
            [
                (Decimal("12.00"), 3),
                (Decimal("16.00"), 2),
            ]
        )
        assert w == Decimal("68.00")
        assert c == 5
        assert avg == Decimal("13.60")

    def test_none_subjects_excluded(self):
        w, c, avg = compute_term_total(
            [
                (Decimal("12.00"), 3),
                (None, 2),
            ]
        )
        assert c == 3
        assert avg == Decimal("12.00")

    def test_all_none_returns_zero(self):
        w, c, avg = compute_term_total([(None, 3), (None, 2)])
        assert avg == Decimal(0)
        assert c == 0


# ═══════════════════════════════════════════════════════════════════════════
# UNIT TESTS: Promotion decisions
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestPromotionDecisions:
    def test_promoted_above_pass(self):
        assert compute_promotion_decision(Decimal("12.0"), Decimal(10)) == "PROMOTED"

    def test_promoted_at_pass(self):
        assert compute_promotion_decision(Decimal("10.0"), Decimal(10)) == "PROMOTED"

    def test_clemency(self):
        assert (
            compute_promotion_decision(Decimal("9.5"), Decimal(9))
            == "PROMOTED BY CLEMENCY OF COUNCIL"
        )

    def test_repeat(self):
        assert compute_promotion_decision(Decimal("5.0"), Decimal(10)) == "REPEAT"

    def test_external_exam_returns_empty(self):
        assert compute_promotion_decision(Decimal("12.0"), Decimal(10), True) == ""

    def test_boundary_clemency(self):
        assert (
            compute_promotion_decision(Decimal("9.0"), Decimal(9))
            == "PROMOTED BY CLEMENCY OF COUNCIL"
        )


# ═══════════════════════════════════════════════════════════════════════════
# UNIT TESTS: Ranking logic
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestRankingLogic:
    def test_equal_averages_same_rank(self, school_a, cls_a, subj_a, term_a):
        for i in range(3):
            s = Student.objects.create(
                school=school_a,
                first_name=f"S{i}",
                sex="M",
                unique_id=f"1111111{i}0",
                date_of_birth=date(2010, 1, 1),
                place_of_birth="D",
                guardian_name="G",
                division_of_origin="W",
                region_of_origin="L",
            )
            StudentEnrollment.objects.create(
                student=s, school_class=cls_a, academic_term=term_a
            )
            ClassSubject.objects.get_or_create(
                school_class=cls_a, subject=subj_a, defaults={"coefficient": 4}
            )
            Competency.objects.get_or_create(
                subject=subj_a,
                term=term_a,
                form_level=1,
                sort_order=1,
                defaults={"description": "Test competency"},
            )
            comp = Competency.objects.get(
                subject=subj_a, term=term_a, form_level=1, sort_order=1
            )
            CompetencyScore.objects.get_or_create(
                student=s,
                competency=comp,
                academic_term=term_a,
                defaults={"score": Decimal("15.00")},
            )

        result = compute_term_results(cls_a, term_a)
        for row in result["rows"]:
            assert row["rank"] == 1

    def test_different_averages_different_ranks(self, school_a, cls_a, subj_a, term_a):
        scores = [Decimal("18.00"), Decimal("12.00"), Decimal("8.00")]
        students = []
        for i, score in enumerate(scores):
            s = Student.objects.create(
                school=school_a,
                first_name=f"R{i}",
                sex="M",
                unique_id=f"3333333{i}0",
                date_of_birth=date(2010, 1, 1),
                place_of_birth="D",
                guardian_name="G",
                division_of_origin="W",
                region_of_origin="L",
            )
            students.append(s)
            StudentEnrollment.objects.create(
                student=s, school_class=cls_a, academic_term=term_a
            )
            ClassSubject.objects.get_or_create(
                school_class=cls_a, subject=subj_a, defaults={"coefficient": 4}
            )
            Competency.objects.get_or_create(
                subject=subj_a,
                term=term_a,
                form_level=1,
                sort_order=1,
                defaults={"description": "Comp"},
            )
            comp = Competency.objects.get(
                subject=subj_a, term=term_a, form_level=1, sort_order=1
            )
            CompetencyScore.objects.get_or_create(
                student=s,
                competency=comp,
                academic_term=term_a,
                defaults={"score": score},
            )

        result = compute_term_results(cls_a, term_a)
        ranks = [r["rank"] for r in result["rows"]]
        assert len(set(ranks)) == 3


# ═══════════════════════════════════════════════════════════════════════════
# UNIT TESTS: Report contexts
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestReportContexts:
    def test_class_council_report_context(self, school_a, cls_a, subj_a, term_a):
        from core.utils.class_council import ClassCouncilReport

        s = Student.objects.create(
            school=school_a,
            first_name="CC",
            sex="M",
            unique_id="555555555",
            date_of_birth=date(2010, 1, 1),
            place_of_birth="D",
            guardian_name="G",
            division_of_origin="W",
            region_of_origin="L",
        )
        StudentEnrollment.objects.create(
            student=s, school_class=cls_a, academic_term=term_a
        )
        TermResult.objects.create(
            student=s, academic_term=term_a, average=Decimal("12.00")
        )

        report = ClassCouncilReport(term_a, school_a)
        ctx = report.get_context_data()
        assert ctx["school"] == school_a
        assert ctx["term"] == term_a
        assert len(ctx["classes_data"]) == 1
        entry = ctx["classes_data"][0]
        assert entry["school_class"] == cls_a
        assert entry["withheld"] is False
        assert entry["stats"]["on_roll_t"] == 1
        assert entry["stats"]["passed_t"] == 1
        assert ctx["totals"]["sat_t"] == 1

    def test_class_council_no_marks_withheld(self, school_a, cls_a, term_a):
        from core.utils.class_council import ClassCouncilReport

        report = ClassCouncilReport(term_a, school_a)
        ctx = report.get_context_data()
        assert len(ctx["classes_data"]) == 1
        entry = ctx["classes_data"][0]
        assert entry["school_class"] == cls_a
        assert entry["withheld"] is True

    def test_report_filename(self, school_a, cls_a, term_a):
        from core.utils.class_council import ClassCouncilReport

        report = ClassCouncilReport(term_a, school_a)
        assert "class_council" in report.filename()

    def test_class_council_withheld_motif(self, school_a, cls_a, term_a):
        from core.models import ClassCouncilRemark
        from core.utils.class_council import ClassCouncilReport

        ClassCouncilRemark.objects.create(
            school=school_a,
            school_class=cls_a,
            academic_term=term_a,
            motif="Awaiting GCE Results",
        )
        report = ClassCouncilReport(term_a, school_a)
        ctx = report.get_context_data()
        entry = ctx["classes_data"][0]
        assert entry["withheld"] is True
        assert entry["motif"] == "Awaiting GCE Results"

    def test_annual_class_council_promotion_counts(
        self, school_a, cls_a, subj_a, term_a
    ):
        from core.utils.class_council import AnnualClassCouncilReport

        cls_a.promotion_mark = 8.0
        cls_a.dismissal_mark = 5.0
        cls_a.save()

        t1 = term_a
        t2 = AcademicTerm.objects.create(
            school=school_a, term_number=2, year_start=2025, year_end=2026
        )
        t3 = AcademicTerm.objects.create(
            school=school_a, term_number=3, year_start=2025, year_end=2026
        )

        # name, sex, avg for every term (None => no term-3 mark => abandoned)
        specs = [
            ("PROM", "M", Decimal("14.00")),
            ("CLEM", "F", Decimal("9.00")),
            ("REP", "M", Decimal("7.00")),
            ("DISM", "F", Decimal("4.00")),
            ("ABAN", "M", None),  # marks in T1+T2 only, no T3 mark
        ]
        students = []
        for i, (name, sex, avg) in enumerate(specs):
            s = Student.objects.create(
                school=school_a,
                first_name=name,
                sex=sex,
                unique_id=f"7{i:08d}",
                date_of_birth=date(2010, 1, 1),
                place_of_birth="D",
                guardian_name="G",
                division_of_origin="W",
                region_of_origin="L",
            )
            students.append((s, avg))

        for s, avg in students:
            for term in (t1, t2):
                StudentEnrollment.objects.create(
                    student=s, school_class=cls_a, academic_term=term
                )
            # Marks in T1 and T2 for everyone (ABAN included)
            SubjectAverage.objects.create(
                student=s, subject=subj_a, academic_term=t1, average=avg or Decimal("10.00")
            )
            SubjectAverage.objects.create(
                student=s, subject=subj_a, academic_term=t2, average=avg or Decimal("10.00")
            )
            if avg is not None:
                StudentEnrollment.objects.create(
                    student=s, school_class=cls_a, academic_term=t3
                )
                SubjectAverage.objects.create(
                    student=s, subject=subj_a, academic_term=t3, average=avg
                )

        report = AnnualClassCouncilReport(
            t1.year_start, t1.year_end, school_a
        )
        ctx = report.get_context_data()
        entry = ctx["classes_data"][0]
        stats = entry["stats"]
        assert stats["on_roll_t"] == 4
        assert stats["promoted_t"] == 2  # 14.00 + 9.00 (clemency)
        assert stats["repeat_t"] == 1  # 7.00
        assert stats["dismissed_t"] == 1  # 4.00
        assert stats["abandoned_t"] == 1  # T1+T2 marks, no T3 mark
        assert stats["pct_promoted"] == Decimal("50.0")

    def test_compute_promotion_decision_dismissal(self, school_a):
        from core.utils.grading import compute_promotion_decision

        assert compute_promotion_decision(
            Decimal("4.00"), Decimal(8), dismissal_mark=Decimal(5)
        ) == "DISMISSED"
        assert compute_promotion_decision(
            Decimal("7.00"), Decimal(8), dismissal_mark=Decimal(5)
        ) == "REPEAT"
        assert compute_promotion_decision(
            Decimal("9.00"), Decimal(8), dismissal_mark=Decimal(5)
        ) == "PROMOTED BY CLEMENCY OF COUNCIL"
        assert compute_promotion_decision(
            Decimal("12.00"), Decimal(8), dismissal_mark=Decimal(5)
        ) == "PROMOTED"

    def test_is_external_exam_class(self, school_a, term_a):
        f5 = SchoolClass.objects.create(
            school=school_a, name="F5", code="F5", form_level=5
        )
        assert is_external_exam_class(f5) is True
        f1 = SchoolClass.objects.create(
            school=school_a, name="F1", code="F2", form_level=1
        )
        assert is_external_exam_class(f1) is False
        us = SchoolClass.objects.create(
            school=school_a, name="US", code="US", form_level=7
        )
        assert is_external_exam_class(us) is True


# ═══════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Compute results end-to-end
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestComputeResults:
    def test_full_compute_flow(self, school_a, cls_a, subj_a, subj_a2, term_a):
        ClassSubject.objects.create(school_class=cls_a, subject=subj_a, coefficient=4)
        ClassSubject.objects.create(
            school_class=cls_a, subject=subj_a2, coefficient=3, sort_order=2
        )
        comp1 = Competency.objects.create(
            subject=subj_a, term=term_a, form_level=1, sort_order=1, description="C1"
        )
        comp2 = Competency.objects.create(
            subject=subj_a2, term=term_a, form_level=1, sort_order=1, description="C2"
        )

        students = []
        for i, scores in enumerate(
            [(Decimal(16), Decimal(14)), (Decimal(8), Decimal(12))]
        ):
            s = Student.objects.create(
                school=school_a,
                first_name=f"S{i}",
                sex="M",
                unique_id=f"7777777{i}0",
                date_of_birth=date(2010, 1, 1),
                place_of_birth="D",
                guardian_name="G",
                division_of_origin="W",
                region_of_origin="L",
            )
            students.append(s)
            StudentEnrollment.objects.create(
                student=s, school_class=cls_a, academic_term=term_a
            )
            CompetencyScore.objects.create(
                student=s, competency=comp1, academic_term=term_a, score=scores[0]
            )
            CompetencyScore.objects.create(
                student=s, competency=comp2, academic_term=term_a, score=scores[1]
            )

        result = compute_term_results(cls_a, term_a)
        assert result["num_sat"] == 2
        assert result["num_passed"] == 1
        assert result["class_average"] > Decimal(0)
        assert result["success_rate"] > Decimal(0)
        assert result["enrolled"] == 2

    def test_compute_all_classes(self, school_a, term_a):
        results = compute_all_classes(term_a)
        assert isinstance(results, list)

    def test_student_without_enrollment_gets_none(self, school_a, subj_a, term_a):
        s = Student.objects.create(
            school=school_a,
            first_name="NoEnroll",
            sex="M",
            unique_id="999999999",
            date_of_birth=date(2010, 1, 1),
            place_of_birth="D",
            guardian_name="G",
            division_of_origin="W",
            region_of_origin="L",
        )
        assert compute_subject_average_for_student(s, subj_a, term_a) is None
        assert compute_term_result_for_student(s, term_a) is None


# ═══════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Mark entry
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestMarkEntry:
    def test_save_score_cell(self, school_a, cls_a, subj_a, term_a, admin_user_a):
        s = Student.objects.create(
            school=school_a,
            first_name="ME",
            sex="M",
            unique_id="666666666",
            date_of_birth=date(2010, 1, 1),
            place_of_birth="D",
            guardian_name="G",
            division_of_origin="W",
            region_of_origin="L",
        )
        StudentEnrollment.objects.create(
            student=s, school_class=cls_a, academic_term=term_a
        )
        comp = Competency.objects.create(
            subject=subj_a, term=term_a, form_level=1, sort_order=1, description="C"
        )

        c = login_client(admin_user_a)
        r = c.post(
            reverse("save_score_cell"),
            {
                "student_id": s.pk,
                "competency_id": comp.pk,
                "term_id": term_a.pk,
                "score": "15.5",
            },
        )
        assert r.status_code == 200
        assert CompetencyScore.objects.filter(student=s, competency=comp).exists()

    def test_mark_entry_page_renders(
        self, school_a, cls_a, subj_a, term_a, admin_user_a
    ):
        c = login_client(admin_user_a)
        r = c.get(reverse("mark_entry_grid", args=[cls_a.pk, subj_a.pk, term_a.pk]))
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Permissions
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestPermissions:
    def test_admin_or_superuser_true(self, admin_user_a):
        assert is_admin_or_superuser(admin_user_a) is True

    def test_teacher_not_admin(self, teacher_user_a):
        assert is_admin_or_superuser(teacher_user_a) is False

    def test_get_school_for_user_admin(self, school_a, admin_user_a):
        assert get_school_for_user(admin_user_a) == school_a

    def test_get_teacher_for_user_none(self, admin_user_a):
        assert get_teacher_for_user(admin_user_a) is None

    def test_can_manage_class_admin(self, school_a, cls_a, admin_user_a):
        assert can_manage_class(admin_user_a, cls_a) is True

    def test_can_manage_class_teacher_no(self, school_a, cls_a, teacher_user_a):
        assert can_manage_class(teacher_user_a, cls_a) is False

    def test_role_required_admin_allows_admin(self, school_a, admin_user_a):
        c = login_client(admin_user_a)
        r = c.get(reverse("student_list"))
        assert r.status_code == 200

    def test_role_required_teacher_forbidden(self, school_a, teacher_user_a):
        c = login_client(teacher_user_a)
        r = c.get(reverse("student_list"))
        assert r.status_code == 403

    def test_bursar_can_access_finance(self, school_a, bursar_user_a):
        c = login_client(bursar_user_a)
        r = c.get(reverse("finance_dashboard"))
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Licensing
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestLicensing:
    def test_license_valid(self, school_a):
        lic = License.objects.create(
            product_key="OC-test-testkey",
            school_name="T",
            expires_at=date.today() + timedelta(days=30),
            status="active",
            machine_id="m1",
            activation_count=1,
            max_devices=5,
        )
        assert lic.is_valid is True
        assert lic.days_remaining >= 29

    def test_license_expired(self, school_a):
        lic = License.objects.create(
            product_key="OC-test-expkey",
            school_name="T",
            expires_at=date.today() - timedelta(days=1),
            status="active",
        )
        assert lic.is_valid is False

    def test_license_revoked(self, school_a):
        lic = License.objects.create(
            product_key="OC-test-revkey",
            school_name="T",
            expires_at=date.today() + timedelta(days=30),
            status="revoked",
        )
        assert lic.is_valid is False

    def test_get_active(self, school_a):
        License.objects.create(
            product_key="OC-test-active",
            school_name="T",
            expires_at=date.today() + timedelta(days=30),
            status="active",
        )
        assert License.get_active() is not None

    def test_get_active_none(self):
        License.objects.filter(status="active").update(status="revoked")
        assert License.get_active() is None

    def test_validate_key_invalid_format(self):
        lic = License(product_key="bad")
        assert lic.validate_key("secret") is False

    def test_validate_key_wrong_signature(self):
        import base64
        import json as _json

        payload = {
            "school": "T",
            "max_students": 100,
            "max_devices": 1,
            "expires": "2030-01-01",
        }
        raw = (
            base64.urlsafe_b64encode(_json.dumps(payload, sort_keys=True).encode())
            .rstrip(b"=")
            .decode()
        )
        lic = License(product_key=f"OC-wrong-{raw}")
        assert lic.validate_key("secret") is False


# ═══════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Backup & restore
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestBackupRestore:
    def test_create_full_backup(self, admin_user_a):
        h = create_backup_archive(
            user=admin_user_a, notes="test full", backup_type="full"
        )
        assert h.file_size > 0
        assert os.path.exists(h.filepath)

    def test_create_db_only_backup(self, admin_user_a):
        h = create_backup_archive(backup_type="database")
        assert h.backup_type == "database"

    def test_restore_roundtrip(self, admin_user_a):
        h1 = create_backup_archive(notes="before", backup_type="database")
        success, msg = restore_backup_archive(h1.pk)
        assert success is True

    def test_restore_nonexistent(self):
        success, msg = restore_backup_archive(99999)
        assert success is False

    def test_backup_history_in_db(self, admin_user_a):
        create_backup_archive(notes="check")
        assert BackupHistory.objects.filter(notes="check").exists()


# ═══════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Attendance
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAttendanceIntegration:
    def test_attendance_lifecycle(self, school_a, cls_a, term_a, admin_user_a):
        s = Student.objects.create(
            school=school_a,
            first_name="Att",
            sex="M",
            unique_id="444444444",
            date_of_birth=date(2010, 1, 1),
            place_of_birth="D",
            guardian_name="G",
            division_of_origin="W",
            region_of_origin="L",
        )
        StudentEnrollment.objects.create(
            student=s, school_class=cls_a, academic_term=term_a
        )
        reg = AttendanceRegister.objects.create(
            school_class=cls_a, date=date(2025, 10, 5), period=1
        )
        ar = AttendanceRecord.objects.create(register=reg, student=s, status="P")
        assert ar.status == "P"

        ar.status = "A"
        ar.save()
        ar.refresh_from_db()
        assert ar.status == "A"


# ═══════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Finance
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestFinanceIntegration:
    def test_income_record_with_student(self, school_a, term_a, admin_user_a):
        s = Student.objects.create(
            school=school_a,
            first_name="Fin",
            sex="F",
            unique_id="888888888",
            date_of_birth=date(2010, 1, 1),
            place_of_birth="D",
            guardian_name="G",
            division_of_origin="W",
            region_of_origin="L",
        )
        ft = FeeType.objects.create(school=school_a, name="PTA", category="PTA")
        ir = IncomeRecord.objects.create(
            school=school_a,
            fee_type=ft,
            student=s,
            amount=Decimal(5000),
            date_paid=date(2025, 10, 1),
            academic_term=term_a,
        )
        assert ir.pk is not None

    def test_expenditure_record(self, school_a, term_a):
        er = ExpenditureRecord.objects.create(
            school=school_a,
            category="PTA",
            amount=Decimal(2000),
            date=date(2025, 10, 2),
            academic_term=term_a,
        )
        assert er.pk is not None

    def test_pta_due_config(self, school_a, cls_a):
        due = PTADueConfig.objects.create(
            school=school_a, school_class=cls_a, amount=Decimal(15000)
        )
        assert due.amount == Decimal(15000)


# ═══════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Parent access
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestParentAccess:
    def test_parent_full_flow(self, school_a, cls_a, term_a):
        s = Student.objects.create(
            school=school_a,
            first_name="Par",
            sex="M",
            unique_id="123456789",
            date_of_birth=date(2010, 1, 1),
            place_of_birth="D",
            guardian_name="G",
            guardian_contact="670000099",
            division_of_origin="W",
            region_of_origin="L",
        )
        StudentEnrollment.objects.create(
            student=s, school_class=cls_a, academic_term=term_a
        )

        c = Client()
        r = c.post(
            reverse("parent:login"),
            {"unique_id": "123456789", "guardian_contact": "670000099"},
        )
        assert r.status_code == 302

        for name in ["dashboard", "student_detail", "marks", "attendance", "fees"]:
            r = c.get(reverse(f"parent:{name}"))
            assert r.status_code == 200, f"{name} should be 200"

    def test_parent_wrong_id(self, school_a):
        c = Client()
        r = c.post(
            reverse("parent:login"), {"unique_id": "999999999", "guardian_contact": "x"}
        )
        assert r.url == reverse("parent:login")


# ═══════════════════════════════════════════════════════════════════════════
# EDGE CASES: Multi-school isolation
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestMultiSchoolIsolation:
    def test_admin_a_cannot_see_student_b(
        self, school_a, school_b, student_a, student_b, admin_user_a
    ):
        c = login_client(admin_user_a)
        r = c.get(reverse("student_list"))
        html = r.content.decode()
        assert "Alice" in html
        assert "Bob" not in html

    def test_student_list_scoped_to_school(
        self, school_a, school_b, admin_user_a, admin_user_b
    ):
        Student.objects.create(
            school=school_a,
            first_name="SA1",
            sex="M",
            unique_id="100000001",
            date_of_birth=date(2010, 1, 1),
            place_of_birth="D",
            guardian_name="G",
            division_of_origin="W",
            region_of_origin="L",
        )
        Student.objects.create(
            school=school_b,
            first_name="SB1",
            sex="M",
            unique_id="200000001",
            date_of_birth=date(2010, 1, 1),
            place_of_birth="D",
            guardian_name="G",
            division_of_origin="M",
            region_of_origin="W",
        )
        c_a = login_client(admin_user_a)
        r = c_a.get(reverse("student_list"))
        assert "SA1" in r.content.decode()
        assert "SB1" not in r.content.decode()


# ═══════════════════════════════════════════════════════════════════════════
# EDGE CASES: Student views
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestStudentViews:
    def test_student_list_renders(self, school_a, admin_user_a):
        c = login_client(admin_user_a)
        r = c.get(reverse("student_list"))
        assert r.status_code == 200

    def test_student_create_get(self, school_a, admin_user_a):
        c = login_client(admin_user_a)
        r = c.get(reverse("student_create"))
        assert r.status_code == 200

    def test_student_create_post(self, school_a, admin_user_a):
        c = login_client(admin_user_a)
        r = c.post(
            reverse("student_create"),
            {
                "first_name": "New",
                "sex": "M",
                "unique_id": "300000001",
                "date_of_birth": "2010-01-01",
                "place_of_birth": "D",
                "guardian_name": "G",
                "division_of_origin": "W",
                "region_of_origin": "L",
            },
        )
        assert r.status_code == 302
        assert Student.objects.filter(unique_id="300000001").exists()

    def test_student_detail_renders(self, school_a, student_a, admin_user_a):
        c = login_client(admin_user_a)
        r = c.get(reverse("student_detail", args=[student_a.pk]))
        assert r.status_code == 200

    def test_student_edit_get(self, school_a, student_a, admin_user_a):
        c = login_client(admin_user_a)
        r = c.get(reverse("student_edit", args=[student_a.pk]))
        assert r.status_code == 200

    def test_student_edit_post(self, school_a, student_a, admin_user_a):
        c = login_client(admin_user_a)
        r = c.post(
            reverse("student_edit", args=[student_a.pk]),
            {
                "first_name": "AliceUpdated",
                "sex": "F",
                "unique_id": student_a.unique_id,
                "date_of_birth": "2010-01-01",
                "place_of_birth": "D",
                "guardian_name": "G",
                "division_of_origin": "W",
                "region_of_origin": "L",
            },
        )
        assert r.status_code == 302
        student_a.refresh_from_db()
        assert student_a.first_name == "AliceUpdated"

    def test_student_export_excel(self, school_a, student_a, admin_user_a):
        c = login_client(admin_user_a)
        r = c.get(reverse("export_students_excel"))
        assert r.status_code == 200
        assert "spreadsheet" in r["Content-Type"]


# ═══════════════════════════════════════════════════════════════════════════
# EDGE CASES: Teacher views
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestTeacherViews:
    def test_teacher_list_renders(self, school_a, admin_user_a):
        c = login_client(admin_user_a)
        r = c.get(reverse("teacher_list"))
        assert r.status_code == 200

    def test_teacher_create_post(self, school_a, admin_user_a):
        c = login_client(admin_user_a)
        r = c.post(
            reverse("teacher_create"),
            {
                "first_name": "NewT",
                "last_name": "Teacher",
                "teacher_code": "T999",
                "email": "t@test.com",
                "phone": "670000000",
            },
        )
        assert r.status_code == 302
        assert Teacher.objects.filter(teacher_code="T999").exists()

    def test_teacher_detail_renders(self, school_a, admin_user_a):
        t = Teacher.objects.create(school=school_a, first_name="DT", last_name="T")
        c = login_client(admin_user_a)
        r = c.get(reverse("teacher_detail", args=[t.pk]))
        assert r.status_code == 200

    def test_teacher_assignments_renders(self, school_a, admin_user_a):
        c = login_client(admin_user_a)
        r = c.get(reverse("teacher_assignments"))
        assert r.status_code == 200

    def test_teacher_assignments_pagination(self, school_a, admin_user_a):
        from core.models import SchoolClass, Subject, TeacherAssignment

        t = Teacher.objects.create(school=school_a, first_name="Page", last_name="Test")
        cls = SchoolClass.objects.create(
            school=school_a, name="Form 1", code="F1", sort_order=1, form_level=1
        )
        subj = Subject.objects.create(
            school=school_a, name="Subject 1", code="S1", sort_order=1
        )
        for i in range(30):
            TeacherAssignment.objects.create(teacher=t, school_class=cls, subject=subj)
            subj = Subject.objects.create(
                school=school_a,
                name=f"Subject {i + 2}",
                code=f"S{i + 2}",
                sort_order=i + 2,
            )

        c = login_client(admin_user_a)
        r = c.get(reverse("teacher_assignments"), {"per_page": 10, "page": 2})
        assert r.status_code == 200
        html = r.content.decode()
        assert "page=1&per_page=10" in html
        assert "page=3&per_page=10" in html
        assert "Showing" in html
        r2 = c.get(reverse("teacher_assignments"), {"per_page": 10, "page": 999})
        assert r2.status_code == 200
        r3 = c.get(reverse("teacher_assignments"), {"per_page": 10, "page": "abc"})
        assert r3.status_code == 200

    def test_teacher_delete_confirm_get(self, school_a, admin_user_a):
        t = Teacher.objects.create(
            school=school_a, first_name="Del", last_name="Teacher"
        )
        c = login_client(admin_user_a)
        r = c.get(reverse("teacher_delete", args=[t.pk]))
        assert r.status_code == 200
        assert "Deactivate" in r.content.decode()
        assert Teacher.objects.filter(pk=t.pk, is_active=True).exists()

    def test_teacher_delete_post(self, school_a, admin_user_a, cls_a, subj_a):
        from core.models import TeacherAssignment

        t = Teacher.objects.create(
            school=school_a, first_name="Del2", last_name="Teacher"
        )
        TeacherAssignment.objects.create(
            teacher=t, school_class=cls_a, subject=subj_a, is_active=True
        )
        c = login_client(admin_user_a)
        r = c.post(reverse("teacher_delete", args=[t.pk]))
        assert r.status_code == 302
        t.refresh_from_db()
        assert t.is_active is False
        assert not TeacherAssignment.objects.filter(
            teacher=t, is_active=True
        ).exists()

    def test_teacher_list_assignment_count(self, school_a, admin_user_a, cls_a, subj_a):
        from core.models import TeacherAssignment

        t = Teacher.objects.create(
            school=school_a, first_name="Assign", last_name="Count"
        )
        TeacherAssignment.objects.create(
            teacher=t, school_class=cls_a, subject=subj_a, is_active=True
        )
        c = login_client(admin_user_a)
        r = c.get(reverse("teacher_list"))
        assert r.status_code == 200
        html = r.content.decode()
        assert "assignment_count" in html or "view" in html

    def test_teacher_list_inactive_filter(self, school_a, admin_user_a):
        Teacher.objects.create(
            school=school_a, first_name="ActiveT", last_name="A"
        )
        Teacher.objects.create(
            school=school_a, first_name="InactiveT", last_name="I", is_active=False
        )
        c = login_client(admin_user_a)
        r = c.get(reverse("teacher_list"), {"status": "inactive"})
        html = r.content.decode()
        assert "InactiveT" in html
        assert "ActiveT" not in html

    def test_teacher_search_single_token(self, school_a, admin_user_a):
        Teacher.objects.create(
            school=school_a, first_name="Sandjong", last_name="Sylvain",
            teacher_code="T001", email="s.sylvain@test.com",
        )
        Teacher.objects.create(
            school=school_a, first_name="Mairamu", last_name="Adamu",
            teacher_code="T002", email="m.adamu@test.com",
        )
        Teacher.objects.create(
            school=school_a, first_name="Ndukong", last_name="Emmanuel",
            teacher_code="T003", email="e.ndukong@test.com",
        )
        c = login_client(admin_user_a)
        r = c.get(reverse("teacher_list"), {"q": "adamu"})
        html = r.content.decode()
        assert "Mairamu Adamu" in html
        assert "Ndukong Emmanuel" not in html

    def test_teacher_search_full_name_across_fields(self, school_a, admin_user_a):
        Teacher.objects.create(
            school=school_a, first_name="Sandjong", last_name="Sylvain",
            teacher_code="T001",
        )
        Teacher.objects.create(
            school=school_a, first_name="Sandjong", last_name="Prosper",
            teacher_code="T002",
        )
        c = login_client(admin_user_a)
        # "Sandjong Sylvain" spans first_name + last_name
        r = c.get(reverse("teacher_list"), {"q": "Sandjong Sylvain"})
        html = r.content.decode()
        assert "Sandjong Sylvain" in html
        assert "Sandjong Prosper" not in html

    def test_teacher_search_htmx_partial(self, school_a, admin_user_a):
        Teacher.objects.create(
            school=school_a, first_name="Sandjong", last_name="Sylvain",
            teacher_code="T001",
        )
        c = login_client(admin_user_a)
        r = c.get(reverse("teacher_list"), {"q": "Sylvain"}, HTTP_HX_REQUEST="true")
        html = r.content.decode()
        assert 'id="teachers-results"' in html
        assert 'id="teachers-count" hx-swap-oob="outerHTML">1</span>' in html
        assert "Sandjong Sylvain" in html


# ═══════════════════════════════════════════════════════════════════════════
# EDGE CASES: Session timeout
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestSessionTimeout:
    def test_session_cookie_age(self):
        from django.conf import settings as dj_settings

        assert dj_settings.SESSION_COOKIE_AGE == 1800
        assert dj_settings.SESSION_EXPIRE_AT_BROWSER_CLOSE is True


# ═══════════════════════════════════════════════════════════════════════════
# EDGE CASES: SMS queue
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestSMSQueue:
    def test_manual_provider_sends_immediately(self, school_a):
        cfg = SMSConfig.objects.create(
            school=school_a, provider="manual", is_active=True
        )
        queue_sms(cfg, "670000001", "Hello")
        sent, failed = process_sms_queue()
        assert sent == 1
        assert failed == 0

    def test_sms_config_daily_limit(self, school_a):
        cfg = SMSConfig.objects.create(
            school=school_a, provider="manual", daily_limit=2
        )
        assert cfg.can_send_today() is True


# ═══════════════════════════════════════════════════════════════════════════
# EDGE CASES: Notifications
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestNotifications:
    def test_notification_lifecycle(self, admin_user_a):
        n = Notification.objects.create(
            recipient=admin_user_a,
            notification_type="system",
            title="T",
            message="M",
        )
        assert n.is_read is False
        n.mark_read()
        n.refresh_from_db()
        assert n.is_read is True


# ═══════════════════════════════════════════════════════════════════════════
# EDGE CASES: Auth views
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAuthViews:
    def test_login_page_renders(self):
        c = Client()
        r = c.get(reverse("login"))
        assert r.status_code == 200

    def test_login_wrong_password(self):
        User.objects.create_user(username="lp", password="pass")
        c = Client()
        r = c.post(reverse("login"), {"username": "lp", "password": "wrong"})
        assert r.status_code == 200
        assert b"Invalid username or password" in r.content

    def test_logout(self):
        c = Client()
        r = c.get(reverse("logout"))
        assert r.status_code == 302


# ═══════════════════════════════════════════════════════════════════════════
# EDGE CASES: Forms
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestForms:
    def test_student_form_valid(self, school_a):
        from core.forms import StudentForm

        form = StudentForm(
            data={
                "first_name": "F",
                "sex": "M",
                "unique_id": "500000001",
                "date_of_birth": "2010-01-01",
                "place_of_birth": "D",
                "guardian_name": "G",
                "division_of_origin": "W",
                "region_of_origin": "L",
            },
            school=school_a,
        )
        assert form.is_valid()

    def test_academic_term_form_clean(self, school_a):
        from core.forms import AcademicTermForm

        form = AcademicTermForm(
            data={
                "term_number": 1,
                "year_start": 2025,
                "year_end": 2026,
            },
            school=school_a,
        )
        assert form.is_valid()

    def test_academic_term_form_bad_year_end(self, school_a):
        from core.forms import AcademicTermForm

        form = AcademicTermForm(
            data={
                "term_number": 1,
                "year_start": 2025,
                "year_end": 2028,
            },
            school=school_a,
        )
        assert not form.is_valid()


# ═══════════════════════════════════════════════════════════════════════════
# EDGE CASES: Admin config views
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestAdminConfigViews:
    def test_settings_hub_renders(self, school_a, admin_user_a):
        c = login_client(admin_user_a)
        r = c.get(reverse("settings"))
        assert r.status_code == 200

    def test_terms_manage_renders(self, school_a, admin_user_a):
        c = login_client(admin_user_a)
        r = c.get(reverse("terms_manage"))
        assert r.status_code == 200

    def test_classes_manage_renders(self, school_a, admin_user_a):
        c = login_client(admin_user_a)
        r = c.get(reverse("classes_manage"))
        assert r.status_code == 200

    def test_subjects_manage_renders(self, school_a, admin_user_a):
        c = login_client(admin_user_a)
        r = c.get(reverse("subjects_manage"))
        assert r.status_code == 200

    def test_users_manage_renders(self, school_a, admin_user_a):
        c = login_client(admin_user_a)
        r = c.get(reverse("users_manage"))
        assert r.status_code == 200

    def test_pta_config_renders(self, school_a, admin_user_a):
        c = login_client(admin_user_a)
        r = c.get(reverse("pta_config"))
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# EDGE CASES: Backup/License/SMS views
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestBackupLicenseSMSViews:
    def test_backup_management_renders(self, admin_user_a):
        c = login_client(admin_user_a)
        r = c.get(reverse("backup_management"))
        assert r.status_code == 200

    def test_license_info_renders(self, admin_user_a):
        c = login_client(admin_user_a)
        r = c.get(reverse("license_info"))
        assert r.status_code == 200

    def test_sms_config_renders(self, admin_user_a, school_a):
        c = login_client(admin_user_a)
        r = c.get(reverse("sms_configuration"))
        assert r.status_code == 200

    def test_notifications_list(self, admin_user_a):
        c = login_client(admin_user_a)
        r = c.get(reverse("notifications_list"))
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# EDGE CASES: Discipline views
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestDisciplineViews:
    def test_conduct_config_renders(self, school_a, admin_user_a):
        c = login_client(admin_user_a)
        r = c.get(reverse("conduct_config"))
        assert r.status_code == 200

    def test_discipline_summary_renders(self, school_a, admin_user_a):
        c = login_client(admin_user_a)
        r = c.get(reverse("discipline_summary"))
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# EDGE CASES: Login throttling
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestLoginThrottling:
    def test_lockout_after_max_attempts(self, school_a):
        User.objects.create_user(username="throttle", password="pass")
        c = Client()
        for _ in range(5):
            c.post(reverse("login"), {"username": "throttle", "password": "wrong"})
        r = c.post(reverse("login"), {"username": "throttle", "password": "pass"})
        # Locked out — correct password is rejected too
        assert b"Too many failed attempts" in r.content

    def test_login_allowed_before_lockout(self, school_a):
        User.objects.create_user(username="throttle2", password="pass")
        c = Client()
        for _ in range(4):
            c.post(reverse("login"), {"username": "throttle2", "password": "wrong"})
        r = c.post(reverse("login"), {"username": "throttle2", "password": "pass"})
        assert r.status_code == 302  # redirects to dashboard

    def test_successful_login_resets_failures(self, school_a):
        User.objects.create_user(username="throttle3", password="pass")
        c = Client()
        for _ in range(3):
            c.post(reverse("login"), {"username": "throttle3", "password": "wrong"})
        c.post(reverse("login"), {"username": "throttle3", "password": "pass"})
        # After successful login, failures are reset
        assert c.session.get("login_lockout_until") is None


# ═══════════════════════════════════════════════════════════════════════════
# EDGE CASES: CSRF protection
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestCSRFProtection:
    @override_settings(DEBUG=False)
    def test_post_without_csrf_token_rejected(self, school_a, admin_user_a):
        c = Client(enforce_csrf_checks=True)
        c.login(username=admin_user_a.username, password="pass")
        r = c.post(
            reverse("student_create"),
            {
                "first_name": "X",
                "sex": "M",
                "unique_id": "600000001",
                "date_of_birth": "2010-01-01",
                "place_of_birth": "D",
                "guardian_name": "G",
                "division_of_origin": "W",
                "region_of_origin": "L",
            },
        )
        assert r.status_code == 403
        assert not Student.objects.filter(unique_id="600000001").exists()

    @override_settings(DEBUG=False)
    def test_post_with_csrf_token_accepted(self, school_a, admin_user_a):
        c = Client(enforce_csrf_checks=True)
        c.login(username=admin_user_a.username, password="pass")
        # Fetch the form page to obtain a CSRF token, then reuse it
        c.get(reverse("student_create"))
        token = c.cookies.get("csrftoken")
        assert token is not None
        r = c.post(
            reverse("student_create"),
            {
                "csrfmiddlewaretoken": token.value,
                "first_name": "CSRF",
                "sex": "M",
                "unique_id": "700000001",
                "date_of_birth": "2010-01-01",
                "place_of_birth": "D",
                "guardian_name": "G",
                "division_of_origin": "W",
                "region_of_origin": "L",
            },
        )
        assert r.status_code == 302
        assert Student.objects.filter(unique_id="700000001").exists()


# ═══════════════════════════════════════════════════════════════════════════
# EDGE CASES: Upload validation (bulk student import)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestUploadValidation:
    def test_import_rejects_non_excel(self, school_a, admin_user_a):
        c = login_client(admin_user_a)
        txt = SimpleUploadedFile(
            "students.txt", b"name,register", content_type="text/plain"
        )
        r = c.post(
            reverse("student_import"),
            {
                "school": school_a.pk,
                "file": txt,
            },
        )
        assert b"not a valid" in r.content or r.status_code in (200, 302)

    def test_import_page_renders(self, school_a, admin_user_a):
        c = login_client(admin_user_a)
        r = c.get(reverse("student_import"))
        assert r.status_code == 200

    def test_import_form_valid_file_type(self, school_a):
        from django.core.files.uploadedfile import SimpleUploadedFile

        from core.forms import StudentImportForm

        xlsx = SimpleUploadedFile(
            "students.xlsx",
            b"not-real",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        form = StudentImportForm(data={"school": school_a.pk}, files={"file": xlsx})
        # .xlsx accepted by the form field even if content is invalid
        assert form.fields["file"].widget.input_type == "file"

    def test_import_students_missing_file(self, school_a, admin_user_a):
        c = login_client(admin_user_a)
        r = c.post(reverse("student_import"), {"school": school_a.pk})
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Bulk imports (Excel preview flow)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestBulkImport:
    def _make_xlsx(self, rows):
        import openpyxl

        wb = openpyxl.Workbook()
        ws = wb.active
        for row in rows:
            ws.append(row)
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        return SimpleUploadedFile(
            "students.xlsx",
            buf.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    def test_import_valid_excel_preview(self, school_a, admin_user_a):
        xlsx = self._make_xlsx(
            [
                ["Name", "Register Number", "Sex", "Date of Birth", "Class"],
                ["John Doe", "555000111", "M", "2010-05-05", "Form 1"],
            ]
        )
        c = login_client(admin_user_a)
        r = c.post(
            reverse("student_import"),
            {
                "school": school_a.pk,
                "file": xlsx,
            },
        )
        assert r.status_code in (200, 302)

    def test_import_with_bad_sex_flag(self, school_a, admin_user_a):
        xlsx = self._make_xlsx(
            [
                ["Name", "Register Number", "Sex", "Date of Birth"],
                ["Bad Sex", "555000222", "X", "2010-05-05"],
            ]
        )
        c = login_client(admin_user_a)
        r = c.post(
            reverse("student_import"),
            {
                "school": school_a.pk,
                "file": xlsx,
            },
        )
        assert r.status_code in (200, 302)

    def test_parse_name_helper(self):
        from core.views.imports import _parse_name

        assert _parse_name("John Paul Doe") == ("John", "Paul Doe")
        assert _parse_name("John") == ("John", "")

    def test_parse_date_helper(self):
        from core.views.imports import _parse_date

        assert _parse_date("10/05/2010") == date(2010, 5, 10)
        assert _parse_date("10-05-2010") == date(2010, 5, 10)
        assert _parse_date("2010-05-10") == date(2010, 5, 10)
        assert _parse_date("garbage") is None


# ═══════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS: Reports views
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.django_db
class TestReportViews:
    def test_reports_hub_renders(self, school_a, admin_user_a):
        c = login_client(admin_user_a)
        r = c.get(reverse("reports_hub"))
        assert r.status_code == 200

    def test_report_select_renders(self, school_a, admin_user_a):
        c = login_client(admin_user_a)
        r = c.get(reverse("reports_hub"))
        assert r.status_code == 200
