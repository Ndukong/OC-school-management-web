from core.models import License, School, Student
from core.utils.permissions import get_school_for_user


def get_tenant(request):
    """Resolve the school tenant for the current request.

    Tenancy is driven by the logged-in user's profile/school. Falls back to the
    first active school only when the user has no explicit school link (e.g. a
    platform superuser before onboarding).
    """
    if not request.user.is_authenticated:
        return None
    school = get_school_for_user(request.user)
    if school is None:
        school = School.objects.filter(is_active=True).first()
    return school


def get_tenant_license(school):
    """Return the active, non-expired license for the given school, or None."""
    if not school:
        return None
    return License.get_active_for_school(school)


def license_lapsed(school) -> bool:
    """True when the school has license records but none currently valid.

    Schools with no license records at all are a platform/dev anomaly and
    keep the legacy dashboard-only behavior; the gate targets the real
    business event: a tenant whose license expired or was revoked.
    """
    if not school:
        return False
    return (
        License.objects.filter(school=school).exists()
        and License.get_active_for_school(school) is None
    )


def tenant_at_student_limit(school) -> bool:
    """True when the school's licensed student quota is exhausted."""
    if not school:
        return False
    license_obj = License.get_active_for_school(school)
    if not license_obj:
        return False
    active_count = Student.objects.filter(school=school, is_active=True).count()
    return active_count >= license_obj.max_students


def tenant_student_slots_remaining(school):
    """Remaining student slots under the active license.

    Returns None when there is no active license (unlimited), otherwise an
    int >= 0.
    """
    if not school:
        return None
    license_obj = License.get_active_for_school(school)
    if not license_obj:
        return None
    active_count = Student.objects.filter(school=school, is_active=True).count()
    remaining = license_obj.max_students - active_count
    return max(0, remaining)
