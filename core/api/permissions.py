from rest_framework.permissions import BasePermission

from core.models import TeacherAssignment
from core.utils.permissions import get_teacher_for_user, is_admin_or_superuser


class IsAdminOrTeacher(BasePermission):
    message = "Only administrators and registered teachers may access this endpoint."

    def has_permission(self, request, view):
        if is_admin_or_superuser(request.user):
            return True
        return get_teacher_for_user(request.user) is not None


class IsAdminOrAssignedTeacher(BasePermission):
    message = "You are not assigned to this class/subject."

    def has_permission(self, request, view):
        if is_admin_or_superuser(request.user):
            return True
        teacher = get_teacher_for_user(request.user)
        if teacher is None:
            return False
        return TeacherAssignment.objects.filter(
            teacher=teacher,
            school_class_id=view.kwargs.get("class_id"),
            subject_id=view.kwargs.get("subject_id"),
            is_active=True,
        ).exists()
