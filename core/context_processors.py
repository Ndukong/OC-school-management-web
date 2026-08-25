from django.conf import settings


def school_context(request):
    """Inject school, license, and role context into every template.

    Tenancy is resolved per request from the logged-in user (see
    core.utils.tenancy.get_tenant), so each school only sees its own data.
    """
    ctx = {"APP_VERSION": getattr(settings, "APP_VERSION", "1.0.0")}

    if not request.user.is_authenticated:
        return ctx

    from core.models import AcademicTerm
    from core.utils.tenancy import get_tenant, get_tenant_license

    school = get_tenant(request)
    ctx["school"] = school
    ctx["license_info"] = _license_dict(get_tenant_license(school))

    if school:
        ctx["current_term"] = (
            AcademicTerm.objects.filter(school=school, is_current=True).first()
        )
    else:
        ctx["current_term"] = None

    user_role = _get_user_role(request.user)
    ctx["user_role"] = user_role
    ctx["is_admin"] = user_role in ("superuser", "admin")
    ctx["is_bursar"] = user_role == "bursar"
    ctx["is_class_master"] = user_role == "class_master"
    ctx["is_teacher"] = user_role == "teacher"

    return ctx


def _get_user_role(user):
    if user.is_superuser:
        profile = getattr(user, "profile", None)
        return profile.role if profile else "superuser"
    profile = getattr(user, "profile", None)
    return profile.role if profile else "teacher"


def parent_context(request):
    """Inject student + school for the parent portal session."""
    ctx = {}
    student_id = request.session.get("parent_student_id")
    if student_id:
        from core.models import School, Student

        student = Student.objects.filter(pk=student_id, is_active=True).first()
        if student is not None:
            ctx["student"] = student
            ctx["school"] = School.objects.filter(pk=student.school_id).first()
            return ctx

    # Login page / no session — still show school name
    from core.models import School
    ctx["school"] = School.objects.filter(is_active=True).first()
    return ctx


def _license_dict(lic):
    if lic is None:
        return None
    return {
        "school_name": lic.school_name,
        "expires_at": lic.expires_at,
        "days_remaining": lic.days_remaining,
        "is_valid": lic.is_valid,
    }
