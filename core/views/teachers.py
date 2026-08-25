from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from core.models import AcademicTerm, SchoolClass, TeacherAssignment
from core.utils.permissions import (
    get_school_for_user,
    get_teacher_for_user,
)


@login_required
def dashboard(request):
    teacher = get_teacher_for_user(request.user)
    school = get_school_for_user(request.user)

    if not school:
        messages.error(request, "No school linked to your account.")
        return render(request, "teachers/dashboard.html", {"assignments": []})

    current_term = AcademicTerm.objects.filter(school=school, is_current=True).first()

    assignments = []
    if teacher:
        qs = TeacherAssignment.objects.filter(
            teacher=teacher, is_active=True
        ).select_related("school_class", "subject")
        for a in qs:
            assignments.append(
                {
                    "class": a.school_class,
                    "subject": a.subject,
                    "is_class_master": a.is_class_master,
                }
            )
    elif request.user.is_superuser or (
        hasattr(request.user, "profile") and request.user.profile.role == "admin"
    ):
        # Admins see all classes/subjects
        for sc in SchoolClass.objects.filter(school=school):
            for cs in sc.subjects.select_related("subject"):
                assignments.append(
                    {
                        "class": sc,
                        "subject": cs.subject,
                        "is_class_master": False,
                    }
                )

    return render(
        request,
        "teachers/dashboard.html",
        {
            "assignments": assignments,
            "current_term": current_term,
            "teacher": teacher,
            "is_finance_user": _is_finance_user(request.user),
            "is_discipline_user": _is_discipline_user(request.user),
        },
    )


def _profile_role(user):
    if hasattr(user, "profile"):
        return user.profile.role
    return None


def _is_finance_user(user):
    if user.is_superuser:
        return True
    return _profile_role(user) in ("admin", "bursar")


def _is_discipline_user(user):
    if user.is_superuser:
        return True
    role = _profile_role(user)
    if role in ("admin", "class_master"):
        return True
    teacher = get_teacher_for_user(user)
    if (
        teacher
        and TeacherAssignment.objects.filter(
            teacher=teacher, is_class_master=True, is_active=True
        ).exists()
    ):
        return True
    return False
