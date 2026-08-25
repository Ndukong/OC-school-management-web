from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from core.models import (
    AcademicTerm,
    ClassSubject,
    Competency,
    CompetencyScore,
    SchoolClass,
    Student,
    Subject,
    SubjectAverage,
    TeacherAssignment,
    TermResult,
)
from core.utils.compute_results import compute_term_results
from core.utils.grading import compute_grade, compute_subject_average
from core.utils.permissions import (
    assignment_required,
    get_school_for_user,
    get_teacher_for_user,
    is_admin_or_superuser,
)


def _get_term(school, term_id=None):
    if term_id:
        return AcademicTerm.objects.filter(pk=term_id, school=school).first()
    return (
        AcademicTerm.objects.filter(school=school, is_current=True).first()
        or AcademicTerm.objects.filter(school=school).first()
    )


def _live_average(student, subject, term):
    enrollment = (
        student.enrollments.filter(academic_term=term)
        .select_related("school_class")
        .first()
    )
    if enrollment is None:
        return None
    competencies = Competency.objects.filter(
        subject=subject, term=term, form_level=enrollment.school_class.form_level
    )
    scores = list(
        CompetencyScore.objects.filter(
            student=student, competency__in=competencies, academic_term=term
        ).values_list("score", flat=True)
    )
    return compute_subject_average([Decimal(str(s)) for s in scores])


def _save_all_scores(post_data, students, competencies, term, teacher):
    """Fallback full-form save used when HTMX is unavailable."""
    errors = []
    saved_count = 0
    with transaction.atomic():
        for student in students:
            for comp in competencies:
                key = f"score_{student.pk}_{comp.pk}"
                raw = post_data.get(key, "").strip()
                if raw == "":
                    CompetencyScore.objects.filter(
                        student=student, competency=comp, academic_term=term
                    ).delete()
                    continue
                try:
                    score = Decimal(raw)
                except InvalidOperation:
                    errors.append(
                        f"Invalid score '{raw}' for {student} / {comp.description[:30]}"
                    )
                    continue
                if score < Decimal(0) or score > Decimal(20):
                    errors.append(f"Score {score} out of range (0-20) for {student}")
                    continue
                CompetencyScore.objects.update_or_create(
                    student=student,
                    competency=comp,
                    academic_term=term,
                    defaults={"score": score, "recorded_by": teacher},
                )
                saved_count += 1
    return errors, saved_count


@login_required
def mark_entry_select(request):
    """Step 1: pick class, subject and term before opening the score grid."""
    school = get_school_for_user(request.user)
    if not school:
        messages.error(request, "No school linked to your account.")
        return redirect("teacher_dashboard")

    teacher = get_teacher_for_user(request.user)

    if is_admin_or_superuser(request.user):
        pairs = [
            (cs.school_class, cs.subject)
            for cs in ClassSubject.objects.filter(school_class__school=school)
            .select_related("school_class", "subject")
            .order_by("school_class__sort_order", "sort_order")
        ]
    else:
        pairs = []
        if teacher:
            pairs = [
                (a.school_class, a.subject)
                for a in TeacherAssignment.objects.filter(
                    teacher=teacher, is_active=True
                )
                .select_related("school_class", "subject")
                .order_by("school_class__sort_order")
            ]

    groups = {}
    for school_class, subject in pairs:
        group = groups.setdefault(school_class, [])
        if not any(s.id == subject.id for s in group):
            group.append(subject)

    terms = list(
        AcademicTerm.objects.filter(school=school).order_by(
            "-year_start", "-term_number"
        )
    )
    current_term = AcademicTerm.objects.filter(
        school=school, is_current=True
    ).first() or (terms[0] if terms else None)

    total_combos = sum(len(subjects) for subjects in groups.values())
    if total_combos == 1:
        school_class = next(iter(groups))
        subject = groups[school_class][0]
        if current_term:
            return redirect(
                "mark_entry_grid",
                class_id=school_class.id,
                subject_id=subject.id,
                term_id=current_term.id,
            )
        return redirect("mark_entry", class_id=school_class.id, subject_id=subject.id)

    selected_term = current_term
    selected_term_id = request.GET.get("term")
    if selected_term_id:
        selected_term = next(
            (t for t in terms if str(t.id) == selected_term_id), selected_term
        )

    return render(
        request,
        "teachers/mark_entry_select.html",
        {
            "school": school,
            "groups": groups,
            "terms": terms,
            "selected_term": selected_term,
            "teacher": teacher,
        },
    )


@login_required
@assignment_required
def mark_entry(request, class_id, subject_id, term_id=None):
    """Students x competencies grid with per-cell auto-save via HTMX."""
    school = get_school_for_user(request.user)
    if not school:
        messages.error(request, "No school linked.")
        return redirect("teacher_dashboard")

    school_class = get_object_or_404(SchoolClass, pk=class_id, school=school)
    subject = get_object_or_404(Subject, pk=subject_id, school=school)
    teacher = get_teacher_for_user(request.user)

    term = _get_term(school, term_id)
    if not term:
        messages.error(request, "No academic term configured.")
        return redirect("teacher_dashboard")

    competencies = list(
        Competency.objects.filter(
            subject=subject, term=term, form_level=school_class.form_level
        ).order_by("sort_order")
    )
    students = list(
        Student.objects.filter(
            enrollments__school_class=school_class,
            enrollments__academic_term=term,
            is_active=True,
        ).order_by("first_name", "other_names")
    )

    existing = {}
    for cs in CompetencyScore.objects.filter(
        student__in=students, competency__in=competencies, academic_term=term
    ):
        existing.setdefault(cs.student_id, {})[cs.competency_id] = cs.score

    is_compute_allowed = is_admin_or_superuser(request.user)
    results = None

    if request.method == "POST":
        if request.POST.get("action") == "compute" and is_compute_allowed:
            errors, _ = _save_all_scores(
                request.POST, students, competencies, term, teacher
            )
            for e in errors[:5]:
                messages.error(request, e)
            results = compute_term_results(school_class, term)
        else:
            errors, saved_count = _save_all_scores(
                request.POST, students, competencies, term, teacher
            )
            for e in errors[:5]:
                messages.error(request, e)
            if saved_count:
                messages.success(request, f"{saved_count} scores saved.")
            return redirect("mark_entry", class_id=class_id, subject_id=subject_id)

    subject_averages = {}
    for sa in SubjectAverage.objects.filter(
        student__in=students, subject=subject, academic_term=term
    ):
        subject_averages[sa.student_id] = sa

    term_results = {}
    for tr in TermResult.objects.filter(student__in=students, academic_term=term):
        term_results[tr.student_id] = tr

    terms = list(
        AcademicTerm.objects.filter(school=school).order_by(
            "-year_start", "-term_number"
        )
    )

    return render(
        request,
        "teachers/mark_entry.html",
        {
            "school_class": school_class,
            "subject": subject,
            "term": term,
            "terms": terms,
            "competencies": competencies,
            "students": students,
            "existing": existing,
            "subject_averages": subject_averages,
            "term_results": term_results,
            "has_computed": bool(subject_averages or term_results),
            "is_compute_allowed": is_compute_allowed,
            "teacher": teacher,
            "results": results,
        },
    )


@login_required
def save_score_cell(request):
    """HTMX endpoint: save (or clear) a single score cell."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    school = get_school_for_user(request.user)
    if not school:
        return JsonResponse({"error": "No school linked to your account."}, status=403)

    try:
        student = Student.objects.get(pk=request.POST.get("student_id"), school=school)
        competency = Competency.objects.select_related("subject").get(
            pk=request.POST.get("competency_id"), subject__school=school
        )
        term = AcademicTerm.objects.get(pk=request.POST.get("term_id"), school=school)
    except (Student.DoesNotExist, Competency.DoesNotExist, AcademicTerm.DoesNotExist):
        return JsonResponse(
            {"error": "Invalid student, competency or term."}, status=400
        )
    except (TypeError, ValueError):
        return JsonResponse(
            {"error": "Invalid student, competency or term."}, status=400
        )

    teacher = get_teacher_for_user(request.user)
    if not is_admin_or_superuser(request.user):
        if teacher is None:
            return JsonResponse(
                {"error": "You are not registered as a teacher."}, status=403
            )
        enrollment = (
            student.enrollments.filter(academic_term=term)
            .select_related("school_class")
            .first()
        )
        if enrollment is None:
            return JsonResponse(
                {"error": "Student is not enrolled in this term."}, status=400
            )
        assigned = TeacherAssignment.objects.filter(
            teacher=teacher,
            school_class=enrollment.school_class,
            subject=competency.subject,
            is_active=True,
        ).exists()
        if not assigned:
            return JsonResponse(
                {"error": "You are not assigned to this class/subject."}, status=403
            )

    raw = request.POST.get("score", "").strip()
    if raw == "":
        CompetencyScore.objects.filter(
            student=student, competency=competency, academic_term=term
        ).delete()
    else:
        try:
            score = Decimal(raw)
        except InvalidOperation:
            return JsonResponse({"error": "Invalid score."}, status=400)
        if score < Decimal(0) or score > Decimal(20):
            return JsonResponse(
                {"error": "Score must be between 0 and 20."}, status=400
            )
        CompetencyScore.objects.update_or_create(
            student=student,
            competency=competency,
            academic_term=term,
            defaults={"score": score, "recorded_by": teacher},
        )

    average = _live_average(student, competency.subject, term)
    return JsonResponse(
        {
            "saved": True,
            "student_id": student.pk,
            "average": str(average) if average is not None else None,
            "grade": compute_grade(average) if average is not None else "",
        }
    )
