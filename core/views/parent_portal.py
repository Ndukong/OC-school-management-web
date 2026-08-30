from decimal import Decimal

from django.contrib import messages
from django.db.models import Count, Sum
from django.shortcuts import redirect, render

from core.models import (
    AcademicTerm,
    AttendanceRecord,
    IncomeRecord,
    PTADueConfig,
    Student,
    StudentEnrollment,
    SubjectAverage,
    TermResult,
)
from core.utils.tenancy import license_lapsed
from core.utils.throttle import BruteForceThrottle, client_ip

SESSION_KEY = "parent_student_id"


def _get_portal_student(request):
    """Return the student scoped to the parent session, or None."""
    student_id = request.session.get(SESSION_KEY)
    if not student_id:
        return None
    return Student.objects.filter(pk=student_id, is_active=True).first()


PARENT_LOGIN_MAX_ATTEMPTS = 5
PARENT_LOGIN_LOCKOUT_MINUTES = 5
PARENT_IP_MAX_ATTEMPTS = 20
PARENT_IP_LOCKOUT_MINUTES = 15

_parent_throttle = BruteForceThrottle("parent_login")


def _parent_throttle_entries(request, unique_id=""):
    """Scopes: the client IP plus the attempted register number."""
    entries = [
        (
            "ip",
            client_ip(request),
            PARENT_IP_MAX_ATTEMPTS,
            PARENT_IP_LOCKOUT_MINUTES,
        )
    ]
    if unique_id:
        entries.append(
            (
                "uid",
                unique_id.strip().lower(),
                PARENT_LOGIN_MAX_ATTEMPTS,
                PARENT_LOGIN_LOCKOUT_MINUTES,
            )
        )
    return entries


def _parent_lockout_remaining(request, unique_id=""):
    lockout, _remaining = _parent_throttle.check(
        _parent_throttle_entries(request, unique_id)
    )
    return lockout


def _record_parent_failure(request, unique_id=""):
    _parent_throttle.record_failure(_parent_throttle_entries(request, unique_id))


def _reset_parent_throttle(request, unique_id=""):
    _parent_throttle.reset(_parent_throttle_entries(request, unique_id))


def parent_login(request):
    if _get_portal_student(request):
        return redirect("parent:dashboard")

    if request.method == "POST":
        unique_id = request.POST.get("unique_id", "").strip()
        guardian_contact = request.POST.get("guardian_contact", "").strip()

        lockout_minutes = _parent_lockout_remaining(request, unique_id)
        if lockout_minutes is not None:
            messages.error(
                request,
                f"Too many failed attempts. Try again in {lockout_minutes} minute(s).",
            )
            return render(request, "parent/login.html")

        matches = list(Student.objects.filter(unique_id=unique_id, is_active=True))

        # Register numbers are school-local, so the same unique_id can exist at
        # several schools. Disambiguate via the guardian contact — cross-tenant
        # access requires knowing BOTH the colliding ID and the matching phone.
        if len(matches) > 1:
            matches = [s for s in matches if s.guardian_contact == guardian_contact]

        if len(matches) != 1 or not matches[0].guardian_contact:
            _record_parent_failure(request, unique_id)
            messages.error(request, "Invalid credentials. Please try again.")
            return redirect("parent:login")

        student = matches[0]
        if student.guardian_contact != guardian_contact:
            _record_parent_failure(request, unique_id)
            messages.error(request, "Invalid credentials. Please try again.")
            return redirect("parent:login")

        if license_lapsed(student.school):
            messages.error(
                request,
                "The school's license has expired. Please contact the school office.",
            )
            return redirect("parent:login")

        _reset_parent_throttle(request, unique_id)
        request.session.cycle_key()
        request.session[SESSION_KEY] = student.pk
        request.session["parent_student_name"] = str(student)
        return redirect("parent:dashboard")

    lockout_minutes = _parent_lockout_remaining(request)
    if lockout_minutes is not None:
        messages.error(
            request,
            f"Too many failed attempts. Try again in {lockout_minutes} minute(s).",
        )
    return render(request, "parent/login.html")


def parent_logout(request):
    request.session.pop(SESSION_KEY, None)
    request.session.pop("parent_student_name", None)
    return redirect("parent:login")


def _require_portal(view_func):
    """Decorator: only allow access when a parent session is active."""

    def wrapper(request, *args, **kwargs):
        student = _get_portal_student(request)
        if student is None:
            return redirect("parent:login")
        if license_lapsed(student.school):
            request.session.pop(SESSION_KEY, None)
            request.session.pop("parent_student_name", None)
            messages.error(
                request,
                "The school's license has expired. Please contact the school office.",
            )
            return redirect("parent:login")
        return view_func(request, student, *args, **kwargs)

    return wrapper


@_require_portal
def parent_dashboard(request, student):
    term = AcademicTerm.objects.filter(school=student.school, is_current=True).first()

    result = None
    if term:
        result = TermResult.objects.filter(student=student, academic_term=term).first()

    attendance = _attendance_summary(student, term)

    expected = _expected_dues(student, term)
    collected = _collected_amount(student, term)
    outstanding = max(expected - collected, Decimal(0))

    return render(
        request,
        "parent/dashboard.html",
        {
            "student": student,
            "term": term,
            "result": result,
            "attendance": attendance,
            "expected": expected,
            "collected": collected,
            "outstanding": outstanding,
        },
    )


@_require_portal
def parent_student_detail(request, student):
    enrollment = (
        StudentEnrollment.objects.filter(student=student)
        .select_related("school_class", "academic_term")
        .order_by(
            "-academic_term__year_start",
            "-academic_term__year_end",
            "-academic_term__term_number",
        )
        .first()
    )

    return render(
        request,
        "parent/student_detail.html",
        {"student": student, "enrollment": enrollment},
    )


@_require_portal
def parent_marks(request, student):
    term = AcademicTerm.objects.filter(school=student.school, is_current=True).first()

    averages = SubjectAverage.objects.none()
    result = None
    if term:
        averages = (
            SubjectAverage.objects.filter(student=student, academic_term=term)
            .select_related("subject")
            .order_by("subject__sort_order")
        )
        result = TermResult.objects.filter(student=student, academic_term=term).first()

    return render(
        request,
        "parent/marks.html",
        {
            "student": student,
            "term": term,
            "averages": averages,
            "result": result,
        },
    )


@_require_portal
def parent_attendance(request, student):
    term = AcademicTerm.objects.filter(school=student.school, is_current=True).first()

    records = AttendanceRecord.objects.none()
    if term:
        class_ids = list(
            StudentEnrollment.objects.filter(
                student=student, academic_term=term
            ).values_list("school_class_id", flat=True)
        )
        if class_ids:
            records = (
                AttendanceRecord.objects.filter(
                    student=student, register__school_class_id__in=class_ids
                )
                .select_related("register")
                .order_by("-register__date")
            )

    return render(
        request,
        "parent/attendance.html",
        {
            "student": student,
            "term": term,
            "records": records,
            "attendance": _attendance_summary(student, term),
        },
    )


@_require_portal
def parent_fees(request, student):
    term = AcademicTerm.objects.filter(school=student.school, is_current=True).first()

    payments = IncomeRecord.objects.none()
    if term:
        payments = (
            IncomeRecord.objects.filter(student=student, academic_term=term)
            .select_related("fee_type")
            .order_by("-date_paid")
        )

    expected = _expected_dues(student, term)
    collected = _collected_amount(student, term)
    outstanding = max(expected - collected, Decimal(0))

    return render(
        request,
        "parent/fees.html",
        {
            "student": student,
            "term": term,
            "payments": payments,
            "expected": expected,
            "collected": collected,
            "outstanding": outstanding,
        },
    )


def _attendance_summary(student, term):
    """Return per-status counts for the current term."""
    summary = {
        "present": 0,
        "absent_justified": 0,
        "absent_unjustified": 0,
        "late": 0,
        "total_days": 0,
    }
    if not term:
        return summary

    enrollments = StudentEnrollment.objects.filter(student=student, academic_term=term)
    class_ids = list(enrollments.values_list("school_class_id", flat=True))

    if not class_ids:
        return summary

    records = (
        AttendanceRecord.objects.filter(
            student=student, register__school_class_id__in=class_ids
        )
        .values("status")
        .annotate(count=Count("id"))
    )

    for row in records:
        key = {
            "P": "present",
            "L": "late",
            "A": "absent_unjustified",
            "PRM": "absent_justified",
        }.get(row["status"])
        if key:
            summary[key] = row["count"]

    summary["total_days"] = sum(
        summary[k]
        for k in ("present", "absent_justified", "absent_unjustified", "late")
    )
    return summary


def _expected_dues(student, term):
    if not term:
        return Decimal(0)
    enrollment = StudentEnrollment.objects.filter(
        student=student, academic_term=term
    ).first()
    if not enrollment:
        return Decimal(0)
    due = PTADueConfig.objects.filter(
        school=student.school, school_class=enrollment.school_class
    ).first()
    return due.amount if due else Decimal(0)


def _collected_amount(student, term):
    if not term:
        return Decimal(0)
    total = IncomeRecord.objects.filter(student=student, academic_term=term).aggregate(
        total=Sum("amount")
    )["total"]
    return total or Decimal(0)
