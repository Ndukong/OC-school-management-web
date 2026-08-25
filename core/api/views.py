from django.db import transaction
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import (
    AcademicTerm,
    Competency,
    CompetencyScore,
    SchoolClass,
    Student,
    Subject,
    TeacherAssignment,
)
from core.utils.permissions import get_school_for_user, get_teacher_for_user

from .permissions import IsAdminOrAssignedTeacher, IsAdminOrTeacher
from .serializers import (
    CompetencyScoreSerializer,
    CompetencySerializer,
    StudentSerializer,
    TeacherAssignmentSerializer,
)


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdminOrTeacher])
def api_assignments(request):
    """Return the teacher's class/subject assignments."""
    teacher = get_teacher_for_user(request.user)
    if not teacher:
        return Response({"error": "Teacher not found"}, status=404)

    qs = TeacherAssignment.objects.filter(
        teacher=teacher, is_active=True
    ).select_related("school_class", "subject")

    term = AcademicTerm.objects.filter(school=teacher.school, is_current=True).first()

    serializer = TeacherAssignmentSerializer(qs, many=True)
    return Response(
        {
            "assignments": serializer.data,
            "current_term": str(term) if term else None,
            "term_id": term.id if term else None,
        }
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdminOrAssignedTeacher])
def api_class_subject(request, class_id, subject_id):
    """Return students + competencies for a class/subject."""
    school = get_school_for_user(request.user)
    if not school:
        return Response({"error": "School not found"}, status=404)

    school_class = SchoolClass.objects.filter(pk=class_id, school=school).first()
    subject = Subject.objects.filter(pk=subject_id, school=school).first()
    if not school_class or not subject:
        return Response({"error": "Class or subject not found"}, status=404)

    term = AcademicTerm.objects.filter(school=school, is_current=True).first()
    if not term:
        term = AcademicTerm.objects.filter(school=school).first()
    if not term:
        return Response({"error": "No term configured"}, status=404)

    competencies = Competency.objects.filter(subject=subject, term=term).order_by(
        "sort_order"
    )

    students = Student.objects.filter(
        enrollments__school_class=school_class,
        enrollments__academic_term=term,
        is_active=True,
    ).order_by("first_name")

    # Existing scores
    scores_qs = CompetencyScore.objects.filter(
        student__in=students,
        competency__in=competencies,
        academic_term=term,
    )
    scores_map = {}
    for s in scores_qs:
        scores_map[f"{s.student_id}_{s.competency_id}"] = str(s.score)

    return Response(
        {
            "class": {"id": school_class.id, "name": str(school_class)},
            "subject": {"id": subject.id, "name": subject.name, "code": subject.code},
            "term": {"id": term.id, "label": str(term)},
            "competencies": CompetencySerializer(competencies, many=True).data,
            "students": StudentSerializer(students, many=True).data,
            "scores": scores_map,
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated, IsAdminOrAssignedTeacher])
def api_save_scores(request, class_id, subject_id):
    """Save scores for a class/subject."""
    school = get_school_for_user(request.user)
    if not school:
        return Response({"error": "School not found"}, status=404)

    school_class = SchoolClass.objects.filter(pk=class_id, school=school).first()
    subject = Subject.objects.filter(pk=subject_id, school=school).first()
    if not school_class or not subject:
        return Response({"error": "Class or subject not found"}, status=404)

    teacher = get_teacher_for_user(request.user)
    term = AcademicTerm.objects.filter(school=school, is_current=True).first()
    if not term:
        return Response({"error": "No current term"}, status=400)

    serializer = CompetencyScoreSerializer(data=request.data, many=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=400)

    with transaction.atomic():
        saved = 0
        for item in serializer.validated_data:
            student = Student.objects.filter(
                pk=item["student_id"], school=school
            ).first()
            competency = Competency.objects.filter(
                pk=item["competency_id"], subject__school=school
            ).first()
            if not student or not competency:
                continue

            if item.get("score") is None:
                CompetencyScore.objects.filter(
                    student=student, competency=competency, academic_term=term
                ).delete()
            else:
                CompetencyScore.objects.update_or_create(
                    student=student,
                    competency=competency,
                    academic_term=term,
                    defaults={"score": item["score"], "recorded_by": teacher},
                )
                saved += 1

    return Response({"saved": saved})
