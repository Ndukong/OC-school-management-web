from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

from core.models import Teacher, TeacherAssignment


def get_teacher_for_user(user):
    """Resolve the Teacher record linked to a user, or None.

    Prefers the explicit UserProfile.teacher link, then matches by
    teacher_code against username, then email, then name.
    """
    if not user or not user.is_authenticated:
        return None
    try:
        profile = user.profile
    except AttributeError:
        profile = None
    if profile and profile.teacher_id:
        return profile.teacher
    teacher = Teacher.objects.filter(teacher_code__iexact=user.username).first()
    if not teacher and user.email:
        teacher = Teacher.objects.filter(email__iexact=user.email).first()
    if not teacher:
        teacher = Teacher.objects.filter(
            first_name__iexact=user.first_name,
            last_name__iexact=user.last_name,
        ).first()
    if not teacher and user.username:
        teacher = Teacher.objects.filter(first_name__iexact=user.username).first()
    return teacher


def get_school_for_user(user):
    """Return the user's school via profile, falling back to their Teacher record."""
    try:
        profile = user.profile
    except AttributeError:
        profile = None
    if profile and profile.school:
        return profile.school
    teacher = get_teacher_for_user(user)
    return teacher.school if teacher else None


def is_admin_or_superuser(user):
    return bool(
        user.is_superuser or (hasattr(user, "profile") and user.profile.role == "admin")
    )


def superuser_required(view_func):
    """Restrict a view to platform superusers only (the system owner)."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return login_required(view_func)(request, *args, **kwargs)
        if not request.user.is_superuser:
            return HttpResponseForbidden(
                "This action is reserved for the platform owner."
            )
        return view_func(request, *args, **kwargs)

    return _wrapped


def can_manage_class(user, school_class) -> bool:
    """Admins and the class master of the given class can manage it."""
    if is_admin_or_superuser(user):
        return True
    teacher = get_teacher_for_user(user)
    if teacher is None:
        return False
    return TeacherAssignment.objects.filter(
        teacher=teacher,
        school_class=school_class,
        is_class_master=True,
        is_active=True,
    ).exists()


def can_view_mark_sheet(user, school_class) -> bool:
    """Admins, the class master, and any teacher assigned to the class.

    Read-only transparency: assigned teachers can see the class mark sheet
    to verify their own marks, but downloads stay admin-only.
    """
    if is_admin_or_superuser(user):
        return True
    teacher = get_teacher_for_user(user)
    if teacher is None:
        return False
    return TeacherAssignment.objects.filter(
        teacher=teacher,
        school_class=school_class,
        is_active=True,
    ).exists()


def role_required(*roles):
    """Allow superuser and admins always; require profile role in ``roles`` otherwise."""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return login_required(view_func)(request, *args, **kwargs)
            if is_admin_or_superuser(request.user) or (
                hasattr(request.user, "profile") and request.user.profile.role in roles
            ):
                return view_func(request, *args, **kwargs)
            return HttpResponseForbidden(
                "You do not have permission to access this page."
            )

        return _wrapped

    return decorator


def assignment_required(view_func):
    """Allow admins, and teachers assigned to the class_id/subject_id in the URL."""

    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return login_required(view_func)(request, *args, **kwargs)
        if is_admin_or_superuser(request.user):
            return view_func(request, *args, **kwargs)
        teacher = get_teacher_for_user(request.user)
        if teacher is None:
            messages.error(request, "You are not registered as a teacher.")
            return redirect("teacher_dashboard")
        assigned = TeacherAssignment.objects.filter(
            teacher=teacher,
            school_class_id=kwargs.get("class_id"),
            subject_id=kwargs.get("subject_id"),
            is_active=True,
        ).exists()
        if not assigned:
            messages.error(request, "You are not assigned to this class/subject.")
            return redirect("teacher_dashboard")
        return view_func(request, *args, **kwargs)

    return _wrapped
