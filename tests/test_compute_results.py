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
    CompetencyScore,
    School,
    SchoolClass,
    Student,
    StudentEnrollment,
    Subject,
    SubjectAverage,
    TermResult,
    UserProfile,
)
from core.utils.compute_results import (
    compute_subject_average_for_student,
    compute_term_result_for_student,
    compute_term_results,
    is_external_exam_class,
)


def make_student(school, school_class, term, uid, sex="M"):
    student = Student.objects.create(
        school=school,
        first_name=f"Student{uid[-3:]}",
        other_names="X",
        sex=sex,
        unique_id=uid,
        date_of_birth=date(2010, 1, 1),
        place_of_birth="Buea",
        guardian_name="Guardian",
        division_of_origin="Fako",
        region_of_origin="South West",
    )
    StudentEnrollment.objects.create(
        student=student, school_class=school_class, academic_term=term
    )
    return student


@pytest.fixture
def data():
    school = School.objects.create(
        name_en="Test School",
        matricule="TEST001",
        region_en="South West",
        division_en="Fako",
    )
    school_class = SchoolClass.objects.create(
        school=school,
        name="Form 1",
        code="F1",
        form_level=1,
        promotion_mark=8.0,
    )
    term = AcademicTerm.objects.create(
        school=school,
        term_number=1,
        year_start=2025,
        year_end=2026,
        is_current=True,
    )
    mat = Subject.objects.create(
        school=school, name="Mathematics", code="MAT", sort_order=1
    )
    eng = Subject.objects.create(
        school=school, name="English", code="ENG", sort_order=2
    )
    ClassSubject.objects.create(
        school_class=school_class, subject=mat, coefficient=2, sort_order=1
    )
    ClassSubject.objects.create(
        school_class=school_class, subject=eng, coefficient=3, sort_order=2
    )
    mat_c1 = Competency.objects.create(
        subject=mat, term=term, form_level=1, description="Compute", sort_order=1
    )
    mat_c2 = Competency.objects.create(
        subject=mat, term=term, form_level=1, description="Solve", sort_order=2
    )
    eng_c1 = Competency.objects.create(
        subject=eng, term=term, form_level=1, description="Read", sort_order=1
    )
    return {
        "school": school,
        "school_class": school_class,
        "term": term,
        "mat": mat,
        "eng": eng,
        "mat_c1": mat_c1,
        "mat_c2": mat_c2,
        "eng_c1": eng_c1,
    }


def add_score(student, competency, term, value):
    CompetencyScore.objects.create(
        student=student,
        competency=competency,
        academic_term=term,
        score=Decimal(str(value)),
    )


@pytest.mark.django_db
class TestSubjectAverage:
    def test_subject_average_computed_and_stored(self, data):
        student = make_student(
            data["school"], data["school_class"], data["term"], "100000001"
        )
        add_score(student, data["mat_c1"], data["term"], 12)
        add_score(student, data["mat_c2"], data["term"], 14)

        result = compute_subject_average_for_student(student, data["mat"], data["term"])

        assert result is not None
        assert result.average == Decimal("13.00")
        assert result.grade == "C+"
        assert result.remark == "CA"

    def test_subject_average_respects_form_level(self, data):
        student = make_student(
            data["school"], data["school_class"], data["term"], "100000002"
        )
        other_level = Competency.objects.create(
            subject=data["mat"],
            term=data["term"],
            form_level=3,
            description="Other level",
            sort_order=9,
        )
        add_score(student, data["mat_c1"], data["term"], 20)
        add_score(student, other_level, data["term"], 2)

        result = compute_subject_average_for_student(student, data["mat"], data["term"])

        assert result.average == Decimal("20.00")

    def test_subject_average_removed_when_no_scores(self, data):
        student = make_student(
            data["school"], data["school_class"], data["term"], "100000003"
        )
        add_score(student, data["mat_c1"], data["term"], 12)
        compute_subject_average_for_student(student, data["mat"], data["term"])
        CompetencyScore.objects.filter(student=student).delete()

        result = compute_subject_average_for_student(student, data["mat"], data["term"])

        assert result is None
        assert not SubjectAverage.objects.filter(
            student=student, subject=data["mat"], academic_term=data["term"]
        ).exists()


@pytest.mark.django_db
class TestTermResult:
    def test_weighted_average(self, data):
        student = make_student(
            data["school"], data["school_class"], data["term"], "100000004"
        )
        add_score(student, data["mat_c1"], data["term"], 10)
        add_score(student, data["mat_c2"], data["term"], 10)
        add_score(student, data["eng_c1"], data["term"], 14)
        compute_subject_average_for_student(student, data["mat"], data["term"])
        compute_subject_average_for_student(student, data["eng"], data["term"])

        result = compute_term_result_for_student(student, data["term"])

        assert result.total_coef == 5
        assert result.total_score == Decimal("62.00")
        assert result.average == Decimal("12.40")
        assert result.grade == "C+"
        assert result.remark == "CA"

    def test_term_result_removed_when_no_scores(self, data):
        student = make_student(
            data["school"], data["school_class"], data["term"], "100000005"
        )
        add_score(student, data["mat_c1"], data["term"], 12)
        compute_term_results(data["school_class"], data["term"])
        assert TermResult.objects.filter(
            student=student, academic_term=data["term"]
        ).exists()

        CompetencyScore.objects.filter(student=student).delete()
        compute_term_results(data["school_class"], data["term"])

        assert not TermResult.objects.filter(
            student=student, academic_term=data["term"]
        ).exists()

    def test_ranking_with_ties(self, data):
        s1 = make_student(
            data["school"], data["school_class"], data["term"], "100000006"
        )
        s2 = make_student(
            data["school"], data["school_class"], data["term"], "100000007"
        )
        s3 = make_student(
            data["school"], data["school_class"], data["term"], "100000008"
        )
        for s in (s1, s2, s3):
            add_score(s, data["mat_c1"], data["term"], 14)
            add_score(s, data["mat_c2"], data["term"], 14)
            add_score(s, data["eng_c1"], data["term"], 14)
        CompetencyScore.objects.filter(
            student=s3, competency=data["eng_c1"], academic_term=data["term"]
        ).update(score=Decimal(2))

        stats = compute_term_results(data["school_class"], data["term"])

        ranks = {r["student"].pk: r["rank"] for r in stats["rows"]}
        assert ranks[s1.pk] == 1
        assert ranks[s2.pk] == 1
        assert ranks[s3.pk] == 3

    def test_promotion_decisions(self, data):
        passed = make_student(
            data["school"], data["school_class"], data["term"], "100000009"
        )
        clemency = make_student(
            data["school"], data["school_class"], data["term"], "100000010"
        )
        repeat = make_student(
            data["school"], data["school_class"], data["term"], "100000011"
        )
        for s in (passed, clemency, repeat):
            add_score(s, data["mat_c1"], data["term"], 14)
            add_score(s, data["mat_c2"], data["term"], 14)
        add_score(clemency, data["eng_c1"], data["term"], 4)
        add_score(repeat, data["eng_c1"], data["term"], 2)

        compute_term_results(data["school_class"], data["term"])

        assert TermResult.objects.get(student=passed).promoted is True
        assert TermResult.objects.get(student=clemency).promoted is True
        assert TermResult.objects.get(student=repeat).promoted is False

    def test_external_exam_class_no_decision(self, data):
        exam_class = SchoolClass.objects.create(
            school=data["school"],
            name="Form 5",
            code="F5",
            form_level=5,
            promotion_mark=8.0,
        )
        ClassSubject.objects.create(
            school_class=exam_class, subject=data["mat"], coefficient=2
        )
        student = make_student(data["school"], exam_class, data["term"], "100000012")
        mat_c = Competency.objects.create(
            subject=data["mat"],
            term=data["term"],
            form_level=5,
            description="Compute",
            sort_order=1,
        )
        add_score(student, mat_c, data["term"], 6)
        compute_subject_average_for_student(student, data["mat"], data["term"])

        assert is_external_exam_class(exam_class)
        result = compute_term_result_for_student(student, data["term"])

        assert result.promoted is None
        assert result.average == Decimal("6.00")


@pytest.mark.django_db
class TestComputeTermResults:
    def test_stats_and_rows(self, data):
        s1 = make_student(
            data["school"], data["school_class"], data["term"], "100000013"
        )
        s2 = make_student(
            data["school"], data["school_class"], data["term"], "100000014"
        )
        make_student(data["school"], data["school_class"], data["term"], "100000015")
        for comp in (data["mat_c1"], data["mat_c2"], data["eng_c1"]):
            add_score(s1, comp, data["term"], 14)
            add_score(s2, comp, data["term"], 6)

        stats = compute_term_results(data["school_class"], data["term"])

        assert stats["enrolled"] == 3
        assert stats["num_sat"] == 2
        assert stats["num_passed"] == 1
        assert stats["class_average"] == Decimal("10.00")
        assert stats["success_rate"] == Decimal("50.0")
        assert len(stats["rows"]) == 2
        assert stats["rows"][0]["rank"] == 1

    def test_recompute_is_idempotent(self, data):
        student = make_student(
            data["school"], data["school_class"], data["term"], "100000016"
        )
        add_score(student, data["mat_c1"], data["term"], 12)
        add_score(student, data["mat_c2"], data["term"], 14)

        compute_term_results(data["school_class"], data["term"])
        compute_term_results(data["school_class"], data["term"])

        assert (
            SubjectAverage.objects.filter(
                student=student, academic_term=data["term"]
            ).count()
            == 1
        )
        assert (
            TermResult.objects.filter(
                student=student, academic_term=data["term"]
            ).count()
            == 1
        )

    def test_stale_average_removed_for_dropped_subject(self, data):
        student = make_student(
            data["school"], data["school_class"], data["term"], "100000017"
        )
        add_score(student, data["mat_c1"], data["term"], 12)
        add_score(student, data["eng_c1"], data["term"], 12)
        compute_term_results(data["school_class"], data["term"])
        assert SubjectAverage.objects.filter(student=student).count() == 2

        ClassSubject.objects.filter(subject=data["eng"]).delete()
        compute_term_results(data["school_class"], data["term"])

        assert SubjectAverage.objects.filter(student=student).count() == 1
        assert not SubjectAverage.objects.filter(
            student=student, subject=data["eng"]
        ).exists()


@pytest.mark.django_db
class TestComputeResultsView:
    def test_requires_login(self):
        response = Client().get(reverse("compute_results"))
        assert response.status_code == 302

    def test_get_renders_form(self, data):
        user = User.objects.create_user(
            username="admin", password="pass", is_staff=True
        )
        UserProfile.objects.create(user=user, school=data["school"], role="admin")
        client = Client()
        client.login(username="admin", password="pass")

        response = client.get(reverse("compute_results"))

        assert response.status_code == 200
        assert "Compute Results" in response.content.decode()

    def test_post_computes_results(self, data):
        student = make_student(
            data["school"], data["school_class"], data["term"], "100000018"
        )
        add_score(student, data["mat_c1"], data["term"], 12)
        add_score(student, data["mat_c2"], data["term"], 14)
        add_score(student, data["eng_c1"], data["term"], 16)
        user = User.objects.create_user(
            username="admin", password="pass", is_staff=True
        )
        UserProfile.objects.create(user=user, school=data["school"], role="admin")
        client = Client()
        client.login(username="admin", password="pass")

        response = client.post(
            reverse("compute_results"),
            {
                "class_id": data["school_class"].id,
                "term_id": data["term"].id,
            },
        )

        assert response.status_code == 200
        assert TermResult.objects.filter(academic_term=data["term"]).count() == 1
        assert TermResult.objects.get(student=student).average == Decimal("14.80")
        assert "Results" in response.content.decode()
