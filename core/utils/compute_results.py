from decimal import Decimal

from core.models import (
    AcademicTerm,
    ClassSubject,
    Competency,
    CompetencyScore,
    SchoolClass,
    Student,
    Subject,
    SubjectAverage,
    TermResult,
)
from core.utils.grading import (
    compute_grade,
    compute_promotion_decision,
    compute_remark,
    compute_subject_average,
    compute_term_total,
)

EXTERNAL_EXAM_FORM_LEVELS = (5, 7)


def is_external_exam_class(school_class: SchoolClass) -> bool:
    """Form 5 and Upper Sixth classes sit state exams and get no promotion decision."""
    return school_class.form_level in EXTERNAL_EXAM_FORM_LEVELS


def _enrolled_class(student: Student, term: AcademicTerm) -> SchoolClass | None:
    enrollment = (
        student.enrollments.filter(academic_term=term)
        .select_related("school_class")
        .first()
    )
    return enrollment.school_class if enrollment else None


def compute_subject_average_for_student(
    student: Student, subject: Subject, term: AcademicTerm
) -> SubjectAverage | None:
    """Derive and persist a student's average for a subject in a term.

    Uses only competencies matching the student's class form level.
    Returns None (and removes any stale average) when no scores exist.
    """
    school_class = _enrolled_class(student, term)
    if school_class is None:
        return None

    competencies = list(
        Competency.objects.filter(
            subject=subject, term=term, form_level=school_class.form_level
        )
    )
    scores = list(
        CompetencyScore.objects.filter(
            student=student, competency__in=competencies, academic_term=term
        ).values_list("score", flat=True)
    )
    average = compute_subject_average([Decimal(str(s)) for s in scores])

    if average is None:
        SubjectAverage.objects.filter(
            student=student, subject=subject, academic_term=term
        ).delete()
        return None

    return SubjectAverage.objects.update_or_create(
        student=student,
        subject=subject,
        academic_term=term,
        defaults={
            "average": average,
            "grade": compute_grade(average),
            "remark": compute_remark(average),
        },
    )[0]


def compute_term_result_for_student(
    student: Student, term: AcademicTerm
) -> TermResult | None:
    """Derive and persist a student's weighted term result.

    Returns None (and removes any stale result) when the student has no
    subject averages for the term.
    """
    school_class = _enrolled_class(student, term)
    if school_class is None:
        return None

    class_subjects = list(ClassSubject.objects.filter(school_class=school_class))
    averages = SubjectAverage.objects.filter(
        student=student,
        academic_term=term,
        subject_id__in=[cs.subject_id for cs in class_subjects],
    )
    avg_map = {sa.subject_id: sa.average for sa in averages}

    weighted = [
        (avg_map[cs.subject_id], cs.coefficient)
        for cs in class_subjects
        if cs.subject_id in avg_map
    ]
    total_weighted, total_coef, overall = compute_term_total(weighted)

    if total_coef == 0:
        TermResult.objects.filter(student=student, academic_term=term).delete()
        return None

    decision = compute_promotion_decision(
        overall,
        Decimal(str(school_class.promotion_mark)),
        is_external_exam_class=is_external_exam_class(school_class),
    )
    promoted = None
    if decision == "PROMOTED" or decision == "PROMOTED BY CLEMENCY OF COUNCIL":
        promoted = True
    elif decision == "REPEAT":
        promoted = False

    return TermResult.objects.update_or_create(
        student=student,
        academic_term=term,
        defaults={
            "total_score": total_weighted.quantize(Decimal("0.01")),
            "total_coef": total_coef,
            "average": overall,
            "grade": compute_grade(overall),
            "remark": compute_remark(overall),
            "promoted": promoted,
        },
    )[0]


def compute_term_results(school_class: SchoolClass, term: AcademicTerm) -> dict:
    """Compute subject averages and term results for a whole class and term.

    Returns a summary dict with display rows, class stats and a promotion
    decision per student. Idempotent: re-running overwrites existing rows.
    """
    students = list(
        Student.objects.filter(
            enrollments__school_class=school_class,
            enrollments__academic_term=term,
            is_active=True,
        )
    )
    class_subjects = list(
        ClassSubject.objects.filter(school_class=school_class)
        .select_related("subject")
        .order_by("sort_order")
    )

    valid_subject_ids = [cs.subject_id for cs in class_subjects]
    SubjectAverage.objects.filter(student__in=students, academic_term=term).exclude(
        subject_id__in=valid_subject_ids
    ).delete()

    for cs in class_subjects:
        for student in students:
            compute_subject_average_for_student(student, cs.subject, term)

    results = []
    for student in students:
        term_result = compute_term_result_for_student(student, term)
        if term_result is not None:
            results.append((student, term_result))

    ranked = sorted(results, key=lambda pair: pair[1].average, reverse=True)
    rank_map = {}
    current_rank = 1
    for i, (_, tr) in enumerate(ranked):
        if i > 0 and tr.average < ranked[i - 1][1].average:
            current_rank = i + 1
        rank_map[tr.pk] = current_rank
    for pk, rank in rank_map.items():
        TermResult.objects.filter(pk=pk).update(rank=rank)
    for _, tr in results:
        tr.refresh_from_db()

    subject_averages = SubjectAverage.objects.filter(
        student__in=[s for s, _ in results], academic_term=term
    )
    avg_map = {(sa.student_id, sa.subject_id): sa.average for sa in subject_averages}

    promotion_mark = Decimal(str(school_class.promotion_mark))
    external = is_external_exam_class(school_class)
    rows = []
    for student, tr in results:
        averages = [avg_map.get((student.pk, cs.subject_id)) for cs in class_subjects]
        decision = compute_promotion_decision(tr.average, promotion_mark, external)
        rows.append(
            {
                "student": student,
                "averages": averages,
                "total_score": tr.total_score,
                "total_coef": tr.total_coef,
                "average": tr.average,
                "rank": tr.rank,
                "grade": tr.grade,
                "remark": tr.remark,
                "promotion_decision": decision,
            }
        )

    num_sat = len(rows)
    num_passed = len([r for r in rows if r["average"] >= Decimal(10)])
    class_average = (
        (sum(r["average"] for r in rows) / Decimal(num_sat)).quantize(Decimal("0.01"))
        if num_sat > 0
        else Decimal(0)
    )
    success_rate = (
        (Decimal(num_passed) / Decimal(num_sat) * Decimal(100)).quantize(
            Decimal("0.1")
        )
        if num_sat > 0
        else Decimal(0)
    )

    return {
        "school_class": school_class,
        "term": term,
        "class_subjects": class_subjects,
        "rows": rows,
        "enrolled": len(students),
        "num_sat": num_sat,
        "num_passed": num_passed,
        "class_average": class_average,
        "success_rate": success_rate,
    }


def compute_all_classes(term: AcademicTerm) -> list[dict]:
    """Compute results for every class of the term's school."""
    classes = SchoolClass.objects.filter(school=term.school).order_by("sort_order")
    return [compute_term_results(school_class, term) for school_class in classes]
