from datetime import date
from decimal import Decimal

import pytest

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
)
from core.utils.report_card import AnnualReportCard, TermReportCard


@pytest.fixture
def data():
    school = School.objects.create(
        name_en="Test School",
        matricule="TEST001",
        region_en="South West",
        division_en="Fako",
    )
    school_class = SchoolClass.objects.create(
        school=school, name="Form 1", code="F1", form_level=1, promotion_mark=8
    )
    term1 = AcademicTerm.objects.create(
        school=school, term_number=1, year_start=2025, year_end=2026, is_current=True
    )
    term2 = AcademicTerm.objects.create(
        school=school, term_number=2, year_start=2025, year_end=2026
    )
    math = Subject.objects.create(school=school, name="Math", code="MAT")
    eng = Subject.objects.create(school=school, name="English", code="ENL")
    ClassSubject.objects.create(
        school_class=school_class, subject=math, coefficient=4, sort_order=1
    )
    ClassSubject.objects.create(
        school_class=school_class, subject=eng, coefficient=2, sort_order=2
    )
    student = Student.objects.create(
        school=school,
        first_name="John",
        other_names="X",
        sex="M",
        unique_id="STU001",
        date_of_birth=date(2010, 1, 1),
        place_of_birth="Buea",
        guardian_name="Guardian",
        division_of_origin="Fako",
        region_of_origin="South West",
    )
    StudentEnrollment.objects.create(
        student=student, school_class=school_class, academic_term=term1
    )
    StudentEnrollment.objects.create(
        student=student, school_class=school_class, academic_term=term2
    )
    return {
        "school": school,
        "school_class": school_class,
        "term1": term1,
        "term2": term2,
        "math": math,
        "eng": eng,
        "student": student,
    }


def make_competency(data, subject, term, description="Competency 1"):
    return Competency.objects.create(
        subject=subject, term=term, form_level=1, description=description
    )


def make_score(data, competency, score):
    return CompetencyScore.objects.create(
        student=data["student"],
        competency=competency,
        academic_term=data["term1"],
        score=score,
    )


@pytest.mark.django_db
class TestTermReportCard:
    def test_rank_and_remark_on_performance_from_term_result(self, data):
        TermResult.objects.create(
            student=data["student"],
            academic_term=data["term1"],
            average=Decimal("12.00"),
            rank=3,
            remark_on_performance="Good effort",
        )

        context = TermReportCard(
            data["student"], data["term1"], data["school"]
        ).get_context_data()

        assert context["rank"] == 3
        assert context["remark_on_performance"] == "Good effort"

    def test_subjects_without_marks_are_hidden(self, data):
        comp = make_competency(data, data["math"], data["term1"])
        make_score(data, comp, Decimal(14))

        context = TermReportCard(
            data["student"], data["term1"], data["school"]
        ).get_context_data()

        subjects = [sd["subject"] for sd in context["subjects_data"]]
        assert subjects == [data["math"]]
        assert context["total_subjects"] == 1

    def test_single_competency_is_repeated(self, data):
        comp = make_competency(data, data["math"], data["term1"], "Add fractions")
        make_score(data, comp, Decimal(14))

        context = TermReportCard(
            data["student"], data["term1"], data["school"]
        ).get_context_data()

        rows = context["subjects_data"][0]["competencies"]
        assert len(rows) == 2
        assert rows[0]["description"] == "Add fractions"
        assert rows[1]["description"] == "Add fractions"

    def test_average_uses_coefficients(self, data):
        math_comp = make_competency(data, data["math"], data["term1"], "Algebra")
        make_score(data, math_comp, Decimal(14))
        eng_comp = make_competency(data, data["eng"], data["term1"], "Reading")
        make_score(data, eng_comp, Decimal(10))

        context = TermReportCard(
            data["student"], data["term1"], data["school"]
        ).get_context_data()

        assert context["total_coef"] == 6
        assert context["total_score"] == Decimal("76.00")
        assert context["average"] == Decimal("12.67")

    def test_rank_is_none_when_no_term_result(self, data):
        comp = make_competency(data, data["math"], data["term1"])
        make_score(data, comp, Decimal(14))

        context = TermReportCard(
            data["student"], data["term1"], data["school"]
        ).get_context_data()

        assert context["rank"] is None


@pytest.mark.django_db
class TestAnnualReportCard:
    def test_annual_filters_subjects_without_marks(self, data):
        math_comp = make_competency(data, data["math"], data["term1"], "Algebra")
        make_score(data, math_comp, Decimal(14))
        SubjectAverage.objects.create(
            student=data["student"],
            subject=data["math"],
            academic_term=data["term1"],
            average=Decimal("14.00"),
        )

        context = AnnualReportCard(
            data["student"], 2025, 2026, data["school"]
        ).get_context_data()

        subjects = [sd["subject"] for sd in context["subjects_data"]]
        assert subjects == [data["math"]]

    def test_annual_average_across_terms(self, data):
        make_competency(data, data["math"], data["term1"], "Algebra")
        SubjectAverage.objects.create(
            student=data["student"],
            subject=data["math"],
            academic_term=data["term1"],
            average=Decimal("14.00"),
        )
        SubjectAverage.objects.create(
            student=data["student"],
            subject=data["math"],
            academic_term=data["term2"],
            average=Decimal("12.00"),
        )

        context = AnnualReportCard(
            data["student"], 2025, 2026, data["school"]
        ).get_context_data()

        assert context["average"] == Decimal("13.00")
        assert context["promotion_decision"] == "PROMOTED"
