import base64
import hashlib
import hmac
import json
import platform
import uuid

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from core.utils.tenancy import get_tenant, get_tenant_license


def login_view(request):
    """Custom login view with school context and failed-attempt throttling."""
    if request.user.is_authenticated:
        return redirect("dashboard")
    school = None

    lockout_time, attempts_remaining = _login_throttle(request)

    if lockout_time is not None:
        messages.error(
            request,
            f"Too many failed attempts. Try again in {lockout_time} minute(s).",
        )
        return render(request, "auth/login.html", {"school": school})

    if request.method == "POST":
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user:
            _reset_login_throttle(request)
            login(request, user)
            next_url = request.GET.get("next", "/")
            if not url_has_allowed_host_and_scheme(
                next_url, allowed_hosts={request.get_host()}
            ):
                next_url = "/"
            return redirect(next_url)
        _record_login_failure(request)
        attempts_remaining = _login_throttle(request)[1]
        if attempts_remaining is not None and attempts_remaining <= 0:
            messages.error(
                request,
                "Too many failed attempts. Please try again in a few minutes.",
            )
        else:
            messages.error(request, "Invalid username or password.")
    return render(request, "auth/login.html", {"school": school})


LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_MINUTES = 5


def _throttle_key(request):
    """Stable key for throttling — forces a session key so it never changes."""
    if not request.session.session_key:
        request.session.save()
    return f"login_failures_{request.session.session_key}"


def _login_throttle(request):
    """Return (lockout_minutes_or_None, attempts_remaining)."""
    key = _throttle_key(request)
    lockout_until = request.session.get("login_lockout_until")
    if lockout_until:
        from django.utils import timezone

        remaining = (lockout_until - timezone.now().timestamp()) / 60
        if remaining > 0:
            return max(1, int(remaining)), 0
        del request.session["login_lockout_until"]

    attempts = request.session.get(key, 0)
    return None, max(0, LOGIN_MAX_ATTEMPTS - attempts)


def _record_login_failure(request):
    key = _throttle_key(request)
    attempts = request.session.get(key, 0) + 1
    request.session[key] = attempts
    if attempts >= LOGIN_MAX_ATTEMPTS:
        from django.utils import timezone

        request.session["login_lockout_until"] = timezone.now().timestamp() + (
            LOGIN_LOCKOUT_MINUTES * 60
        )


def _reset_login_throttle(request):
    key = _throttle_key(request)
    request.session.pop(key, None)
    request.session.pop("login_lockout_until", None)


def logout_view(request):
    logout(request)
    return redirect("login")


def dashboard(request):
    """Role-aware dashboard dispatcher."""
    if not request.user.is_authenticated:
        return redirect("login")

    school = get_tenant(request)
    if school is None:
        messages.warning(
            request,
            "Your account is not linked to a school. Please complete activation.",
        )
        return redirect("activate")

    license_info = get_tenant_license(school)
    if not license_info:
        messages.warning(request, "No valid license found. Please activate the system.")
        return redirect("activate")

    from core.models import AcademicTerm

    current_term = None
    if school:
        current_term = AcademicTerm.objects.filter(
            school=school, is_current=True
        ).first()

    user_role = _get_user_role(request.user)

    ctx = {
        "school": school,
        "current_term": current_term,
        "license_info": _license_dict(license_info),
        "user_role": user_role,
        "APP_VERSION": settings.APP_VERSION,
    }

    if user_role in ("superuser", "admin"):
        return _admin_dashboard(request, ctx)
    elif user_role == "bursar":
        return _bursar_dashboard(request, ctx)
    elif user_role == "class_master":
        return _class_master_dashboard(request, ctx)
    return _teacher_dashboard(request, ctx)


def activate_view(request):
    """License activation and setup wizard (multi-tenant safe).

    Each product key activates its own License, School, and admin account.
    The in-progress activation is tracked via ``activate_license_id`` in the
    session so the wizard steps stay scoped to one school.
    """
    from core.models import License

    pending_id = request.session.get("activate_license_id")
    license_obj = License.objects.filter(pk=pending_id).first() if pending_id else None

    raw_step = (
        request.POST.get("step", "1")
        if request.method == "POST"
        else request.GET.get("step", "1")
    )
    try:
        step = int(raw_step)
    except (TypeError, ValueError):
        step = 1

    if request.method == "POST":
        if step == 1:
            return _activate_license(request)
        elif step == 2:
            return _setup_school(request, license_obj)
        elif step == 3:
            return _setup_admin(request, license_obj)

    school = license_obj.school if license_obj else None
    ctx = {
        "step": _activation_step(license_obj),
        "license": license_obj,
        "license_info": _license_dict(license_obj) if license_obj else None,
        "school": school,
    }
    return render(request, "auth/activate.html", ctx)


def _activation_step(license_obj):
    from core.models import UserProfile

    if not license_obj:
        return 1
    if not license_obj.school:
        return 2
    if not UserProfile.objects.filter(
        school=license_obj.school, role="admin"
    ).exists():
        return 3
    return 4


def _activate_license(request):
    """Step 1: Validate and activate a product key (creates the License row)."""
    from datetime import date as date_type

    from core.models import License

    key = request.POST.get("product_key", "").strip()
    if not key:
        messages.error(request, "Please enter a product key.")
        return redirect("activate")

    existing = License.objects.filter(product_key=key).first()
    if existing:
        messages.info(request, "This license key has already been activated.")
        request.session["activate_license_id"] = existing.pk
        return redirect("activate")

    parts = key.split("-", 2)
    if len(parts) != 3 or parts[0] != "OC":
        messages.error(request, "Invalid product key format.")
        return redirect("activate")

    signature = parts[1]
    raw = parts[2]
    padding = 4 - len(raw) % 4
    raw_padded = raw + "=" * padding
    try:
        payload_bytes = base64.urlsafe_b64decode(raw_padded)
        payload = json.loads(payload_bytes)
    except (TypeError, ValueError):
        messages.error(request, "Invalid product key.")
        return redirect("activate")

    expected = hmac.new(
        settings.LICENSE_SECRET_KEY.encode(),
        json.dumps(payload, sort_keys=True).encode(),
        hashlib.sha256,
    ).hexdigest()[:16]
    if not hmac.compare_digest(signature, expected):
        messages.error(request, "Invalid product key - signature mismatch.")
        return redirect("activate")

    machine_id = hashlib.sha256(
        (platform.node() + str(uuid.getnode())).encode()
    ).hexdigest()[:64]

    license = License.objects.create(
        product_key=key,
        school_name=payload["school"],
        max_students=payload.get("max_students", 500),
        max_devices=payload.get("max_devices", 3),
        expires_at=date_type.fromisoformat(payload["expires"]),
        activated_at=timezone.now(),
        machine_id=machine_id,
        activation_count=1,
    )
    request.session["activate_license_id"] = license.pk

    messages.success(request, f"License activated for {license.school_name}!")
    return redirect("activate")


def _setup_school(request, license_obj):
    """Step 2: Configure the school profile for this license."""
    from core.models import School

    if not license_obj:
        return redirect("activate")

    school = license_obj.school
    if school is None:
        school = School.objects.create(
            matricule="PENDING",
            name_en=license_obj.school_name,
            region_en=request.POST.get("region_en", "").strip(),
            division_en=request.POST.get("division_en", "").strip(),
        )
        license_obj.school = school
        license_obj.save()

    school.name_en = request.POST.get("name_en", "").strip() or school.name_en
    school.region_en = request.POST.get("region_en", "").strip() or school.region_en
    school.division_en = (
        request.POST.get("division_en", "").strip() or school.division_en
    )
    school.phone = request.POST.get("phone", "").strip() or school.phone
    school.motto_en = request.POST.get("motto_en", "").strip() or school.motto_en

    if request.FILES.get("logo"):
        school.logo = request.FILES["logo"]
    if request.FILES.get("seal"):
        school.seal = request.FILES["seal"]

    if school.matricule == "PENDING":
        school.matricule = f"SCH-{school.pk:04d}"

    school.save()

    from django.core.management import call_command

    try:
        call_command("seed_default_config", "--school", str(school.pk), "--auto")
    except Exception:
        pass

    return redirect("activate")


def _setup_admin(request, license_obj):
    """Step 3: Create the admin account linked to this license's school."""
    from core.models import UserProfile

    if not license_obj or not license_obj.school:
        return redirect("activate")

    school = license_obj.school

    username = request.POST.get("username", "").strip()
    password = request.POST.get("password", "")
    password2 = request.POST.get("password_confirm", "")
    first_name = request.POST.get("first_name", "").strip()
    last_name = request.POST.get("last_name", "").strip()
    email = request.POST.get("email", "").strip()

    if not username or not password:
        messages.error(request, "Username and password are required.")
        return redirect("activate")
    if password != password2:
        messages.error(request, "Passwords do not match.")
        return redirect("activate")
    if len(password) < 6:
        messages.error(request, "Password must be at least 6 characters.")
        return redirect("activate")
    if User.objects.filter(username=username).exists():
        messages.error(
            request,
            "That username is already taken. Please choose another.",
        )
        return redirect("activate")

    user = User.objects.create_user(
        username=username,
        password=password,
        first_name=first_name,
        last_name=last_name,
        email=email,
        is_staff=False,
        is_superuser=False,
    )
    UserProfile.objects.create(user=user, school=school, role="admin")

    request.session.pop("activate_license_id", None)

    messages.success(
        request, f'Admin account "{username}" created. You can now log in.'
    )
    return redirect("activate")


def _get_school_context():
    from core.models import School

    return School.objects.filter(is_active=True).first()


def _get_user_role(user):
    if user.is_superuser:
        profile = getattr(user, "profile", None)
        return profile.role if profile else "superuser"
    profile = getattr(user, "profile", None)
    return profile.role if profile else "teacher"


def _license_dict(lic):
    if lic is None:
        return None
    return {
        "school_name": lic.school_name,
        "expires_at": lic.expires_at,
        "days_remaining": lic.days_remaining,
        "is_valid": lic.is_valid,
    }


def _profile_role(user):
    profile = getattr(user, "profile", None)
    return profile.role if profile else None


def _is_finance_user(user):
    if user.is_superuser:
        return True
    return _profile_role(user) in ("admin", "bursar")


def _is_discipline_user(user):
    if user.is_superuser:
        return True
    if _profile_role(user) in ("admin", "class_master"):
        return True

    from core.models import TeacherAssignment
    from core.utils.permissions import get_teacher_for_user

    teacher = get_teacher_for_user(user)
    return bool(
        teacher
        and TeacherAssignment.objects.filter(
            teacher=teacher, is_class_master=True, is_active=True
        ).exists()
    )


def _admin_dashboard(request, ctx):
    from core.models import SchoolClass, Student, Teacher

    school = ctx["school"]
    current_term = ctx["current_term"]
    if school:
        ctx["total_students"] = Student.objects.filter(
            school=school, is_active=True
        ).count()
        ctx["total_teachers"] = Teacher.objects.filter(
            school=school, is_active=True
        ).count()
        ctx["total_classes"] = SchoolClass.objects.filter(school=school).count()
        if current_term:
            ctx["total_enrolled"] = (
                Student.objects.filter(
                    enrollments__academic_term=current_term, is_active=True
                )
                .distinct()
                .count()
            )
    return render(request, "dashboard/admin.html", ctx)


def _bursar_dashboard(request, ctx):
    from core.models import ExpenditureRecord, IncomeRecord

    school = ctx["school"]
    current_term = ctx["current_term"]
    if school and current_term:
        ctx["term_income"] = (
            IncomeRecord.objects.filter(
                school=school, academic_term=current_term
            ).total_amount()
            if hasattr(IncomeRecord.objects, "total_amount")
            else 0
        )
        ctx["term_expenditure"] = (
            ExpenditureRecord.objects.filter(
                school=school, academic_term=current_term
            ).total_amount()
            if hasattr(ExpenditureRecord.objects, "total_amount")
            else 0
        )
    return render(request, "dashboard/bursar.html", ctx)


def _class_master_dashboard(request, ctx):
    from core.models import AttendanceRegister, DisciplineSummary, TeacherAssignment
    from core.utils.permissions import get_teacher_for_user

    teacher = get_teacher_for_user(request.user)
    if teacher:
        assignments = TeacherAssignment.objects.filter(
            teacher=teacher, is_active=True, is_class_master=True
        ).select_related("school_class", "subject")
        ctx["master_classes"] = [a.school_class for a in assignments]

        class_ids = [sc.id for sc in ctx["master_classes"]]
        ctx["class_attendance"] = {}
        ctx["pending_discipline"] = 0
        if class_ids:
            from datetime import timedelta

            today = timezone.localdate()
            week_start = today - timedelta(days=today.weekday())

            stats = {cid: {"records": 0, "present": 0} for cid in class_ids}
            registers = AttendanceRegister.objects.filter(
                school_class_id__in=class_ids, date__range=(week_start, today)
            ).prefetch_related("records")
            for register in registers:
                row = stats[register.school_class_id]
                for record in register.records.all():
                    row["records"] += 1
                    if record.status == "P":
                        row["present"] += 1

            ctx["class_attendance"] = {
                cid: {
                    "total": row["records"],
                    "present": row["present"],
                    "percent": (
                        round(100 * row["present"] / row["records"], 1)
                        if row["records"]
                        else 0
                    ),
                }
                for cid, row in stats.items()
            }

            current_term = ctx.get("current_term")
            if current_term:
                ctx["pending_discipline"] = (
                    DisciplineSummary.objects.filter(
                        academic_term=current_term,
                        student__enrollments__school_class_id__in=class_ids,
                    )
                    .exclude(conduct_decision="")
                    .values_list("student_id", flat=True)
                    .distinct()
                    .count()
                )
    return render(request, "dashboard/class_master.html", ctx)


def _teacher_dashboard(request, ctx):
    from core.models import SchoolClass, TeacherAssignment
    from core.utils.permissions import get_teacher_for_user

    teacher = get_teacher_for_user(request.user)
    if teacher:
        qs = TeacherAssignment.objects.filter(
            teacher=teacher, is_active=True
        ).select_related("school_class", "subject")
        ctx["assignments"] = [
            {
                "class": a.school_class,
                "subject": a.subject,
                "is_class_master": a.is_class_master,
            }
            for a in qs
        ]
    elif request.user.is_superuser or (
        hasattr(request.user, "profile") and request.user.profile.role == "admin"
    ):
        school = ctx["school"]
        if school:
            assignments = []
            for sc in SchoolClass.objects.filter(school=school):
                for cs in sc.subjects.select_related("subject"):
                    assignments.append(
                        {
                            "class": sc,
                            "subject": cs.subject,
                            "is_class_master": False,
                        }
                    )
            ctx["assignments"] = assignments
    else:
        ctx["assignments"] = []

    ctx["is_finance_user"] = _is_finance_user(request.user)
    ctx["is_discipline_user"] = _is_discipline_user(request.user)

    return render(request, "teachers/dashboard.html", ctx)
