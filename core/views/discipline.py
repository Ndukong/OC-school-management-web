from datetime import date as date_cls

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from core.forms import PunishmentForm
from core.models import (
    AcademicTerm,
    AttendanceRecord,
    AttendanceRegister,
    ConductThreshold,
    Punishment,
    SchoolClass,
    Student,
)
from core.utils.discipline import compute_discipline_summaries
from core.utils.permissions import (
    can_manage_class,
    get_school_for_user,
    get_teacher_for_user,
    is_admin_or_superuser,
)

STATUS_CHOICES = [
    ("P", "Present"),
    ("L", "Late"),
    ("A", "Absent"),
    ("PRM", "Permission"),
]

VALID_STATUSES = {status for status, _ in STATUS_CHOICES}

# Click cycle on a grid cell: unmarked → P → L → A → PRM → unmarked.
_CYCLE_ORDER = ["P", "L", "A", "PRM"]


def _next_status(current: str) -> str:
    if current not in _CYCLE_ORDER:
        return "P"
    idx = _CYCLE_ORDER.index(current)
    if idx == len(_CYCLE_ORDER) - 1:
        return ""
    return _CYCLE_ORDER[idx + 1]


def _day_summary(records) -> dict:
    """Aggregate status counts across all periods for a day."""
    counts = list(records)
    return {
        "present": sum(1 for s in counts if s == "P"),
        "late": sum(1 for s in counts if s == "L"),
        "absent": sum(1 for s in counts if s == "A"),
        "permission": sum(1 for s in counts if s == "PRM"),
        "total": len(counts),
    }


def _parse_date(raw):
    if not raw:
        return None
    try:
        return date_cls.fromisoformat(raw)
    except ValueError:
        return None


@login_required
def attendance_entry(request):
    school = get_school_for_user(request.user)
    if not school:
        messages.error(request, "No school linked to your account.")
        return redirect("teacher_dashboard")

    classes = SchoolClass.objects.filter(school=school)
    teacher = get_teacher_for_user(request.user)

    class_id = request.GET.get("class_id") or request.POST.get("class_id")
    date_raw = request.GET.get("date") or request.POST.get("date")
    selected_date = _parse_date(date_raw) or date_cls.today()

    periods = list(range(1, school.periods_per_day + 1))

    school_class = None
    students = []
    records_by_period = {}
    summary = {"present": 0, "late": 0, "absent": 0, "permission": 0, "total": 0}

    if class_id:
        school_class = get_object_or_404(SchoolClass, pk=class_id, school=school)
        if not can_manage_class(request.user, school_class):
            messages.error(request, "You are not the class master of this class.")
            return redirect("teacher_dashboard")
        term = (
            AcademicTerm.objects.filter(school=school, is_current=True).first()
            or AcademicTerm.objects.filter(school=school).first()
        )
        students = list(
            Student.objects.filter(
                enrollments__school_class=school_class,
                enrollments__academic_term=term,
                is_active=True,
            ).order_by("first_name")
        )

    if request.method == "POST" and request.POST.get("action") == "save":
        saved_count = 0
        for period in periods:
            posted = {
                student.pk: request.POST.get(f"status_{student.pk}_{period}", "").strip()
                for student in students
            }
            marks = {
                pk: status for pk, status in posted.items() if status in VALID_STATUSES
            }
            if not marks:
                continue
            register, _ = AttendanceRegister.objects.update_or_create(
                school_class=school_class,
                date=selected_date,
                period=period,
                defaults={"recorded_by": teacher},
            )
            for student in students:
                status = posted.get(student.pk, "")
                if status in VALID_STATUSES:
                    AttendanceRecord.objects.update_or_create(
                        register=register,
                        student=student,
                        defaults={"status": status},
                    )
                    saved_count += 1
                else:
                    AttendanceRecord.objects.filter(
                        register=register, student=student
                    ).delete()
        messages.success(
            request,
            f"Attendance saved for {saved_count} marks ({selected_date}).",
        )
        url = reverse("attendance_entry")
        return redirect(
            f"{url}?class_id={school_class.id}&date={selected_date.isoformat()}"
        )

    if school_class:
        records_by_period = {period: {} for period in periods}
        all_statuses = []
        registers = AttendanceRegister.objects.filter(
            school_class=school_class, date=selected_date
        ).prefetch_related("records")
        for register in registers:
            records_by_period[register.period] = {
                r.student_id: r.status for r in register.records.all()
            }
            all_statuses.extend(r.status for r in register.records.all())
        summary = _day_summary(all_statuses)

    return render(
        request,
        "discipline/attendance.html",
        {
            "classes": classes,
            "school_class": school_class,
            "selected_date": selected_date,
            "students": students,
            "periods": periods,
            "records_by_period": records_by_period,
            "status_choices": STATUS_CHOICES,
            "summary": summary,
        },
    )


@login_required
def discipline_summary_view(request):
    school = get_school_for_user(request.user)
    if not school:
        messages.error(request, "No school linked to your account.")
        return redirect("teacher_dashboard")

    classes = SchoolClass.objects.filter(school=school)
    terms = AcademicTerm.objects.filter(school=school)

    school_class = None
    term = None
    results = None
    punishment_form = None

    class_id = request.GET.get("class_id") or request.POST.get("class_id")
    term_id = request.GET.get("term_id") or request.POST.get("term_id")

    if class_id:
        school_class = get_object_or_404(SchoolClass, pk=class_id, school=school)
        if not can_manage_class(request.user, school_class):
            messages.error(request, "You are not the class master of this class.")
            return redirect("teacher_dashboard")
    if term_id:
        term = get_object_or_404(AcademicTerm, pk=term_id, school=school)

    if request.method == "POST":
        if request.POST.get("add_punishment") and school_class and term:
            students = Student.objects.filter(
                enrollments__school_class=school_class,
                enrollments__academic_term=term,
                is_active=True,
            )
            form = PunishmentForm(request.POST, students=students)
            if form.is_valid():
                data = {k: v for k, v in form.cleaned_data.items() if k != "student"}
                Punishment.objects.create(
                    student=form.cleaned_data["student"],
                    academic_term=term,
                    recorded_by=get_teacher_for_user(request.user),
                    **data,
                )
                messages.success(request, "Punishment recorded.")
            else:
                messages.error(request, "Punishment form is invalid.")
            return redirect(
                f"{reverse('discipline_summary')}?class_id={school_class.id}&term_id={term.id}"
            )
        messages.error(request, "Select a class and term first.")

    if school_class and term:
        results = compute_discipline_summaries(school_class, term)
        students = Student.objects.filter(
            enrollments__school_class=school_class,
            enrollments__academic_term=term,
            is_active=True,
        )
        punishment_form = PunishmentForm(students=students)

    thresholds = ConductThreshold.objects.filter(school=school)
    return render(
        request,
        "discipline/summary.html",
        {
            "classes": classes,
            "terms": terms,
            "school_class": school_class,
            "term": term,
            "results": results,
            "punishment_form": punishment_form,
            "thresholds": thresholds,
        },
    )


@login_required
def save_attendance_cell(request):
    """HTMX endpoint: cycle a single student's status for one class/date/period."""
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    school = get_school_for_user(request.user)
    if not school:
        return JsonResponse({"error": "No school linked"}, status=403)

    try:
        school_class = SchoolClass.objects.get(
            pk=request.POST.get("class_id"), school=school
        )
        student = Student.objects.get(
            pk=request.POST.get("student_id"), school=school
        )
        period = int(request.POST.get("period", ""))
        selected_date = _parse_date(request.POST.get("date"))
    except (SchoolClass.DoesNotExist, Student.DoesNotExist, TypeError, ValueError):
        return JsonResponse({"error": "Invalid register or student."}, status=400)

    if selected_date is None or period < 1 or period > school.periods_per_day:
        return JsonResponse({"error": "Invalid date or period."}, status=400)

    if not can_manage_class(request.user, school_class):
        return JsonResponse({"error": "Not authorized for this class."}, status=403)

    current = request.POST.get("status", "").strip()
    status = _next_status(current)

    register, _ = AttendanceRegister.objects.get_or_create(
        school_class=school_class, date=selected_date, period=period
    )
    if status:
        AttendanceRecord.objects.update_or_create(
            register=register, student=student, defaults={"status": status}
        )
    else:
        AttendanceRecord.objects.filter(register=register, student=student).delete()

    day_registers = AttendanceRegister.objects.filter(
        school_class=school_class, date=selected_date
    )
    day_statuses = AttendanceRecord.objects.filter(
        register__in=day_registers
    ).values_list("status", flat=True)
    summary = _day_summary(day_statuses)

    return JsonResponse({"saved": True, "status": status, "summary": summary})


@login_required
def conduct_config(request):
    """Configure conduct thresholds for the school."""
    school = get_school_for_user(request.user)
    if not school:
        messages.error(request, "No school linked to your account.")
        return redirect("dashboard")

    if not is_admin_or_superuser(request.user):
        messages.error(request, "Only administrators can configure conduct thresholds.")
        return redirect("dashboard")

    if request.method == "POST":
        for conduct_type in ["warning", "reprimand", "suspension", "dismissal"]:
            threshold, _ = ConductThreshold.objects.get_or_create(
                school=school, conduct_type=conduct_type
            )
            threshold.min_unjustified_abs = int(request.POST.get(f"min_ua_{conduct_type}", 0) or 0)
            threshold.min_justified_abs = int(request.POST.get(f"min_ja_{conduct_type}", 0) or 0)
            threshold.min_lateness = int(request.POST.get(f"min_lat_{conduct_type}", 0) or 0)
            from decimal import Decimal
            threshold.min_punishment_hours = Decimal(request.POST.get(f"min_ph_{conduct_type}", 0) or 0)
            threshold.save()
        messages.success(request, "Conduct thresholds updated.")
        return redirect("conduct_config")

    thresholds = {}
    for t in ConductThreshold.objects.filter(school=school):
        thresholds[t.conduct_type] = t

    conduct_types = [
        {"value": "warning", "label": "Warning"},
        {"value": "reprimand", "label": "Reprimand"},
        {"value": "suspension", "label": "Suspension"},
        {"value": "dismissal", "label": "Dismissal"},
    ]
    for ct in conduct_types:
        ct["threshold"] = thresholds.get(ct["value"])
    return render(request, "discipline/conduct_config.html", {"conduct_types": conduct_types})
