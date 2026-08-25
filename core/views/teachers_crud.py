from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from core.forms import TeacherAssignmentForm, TeacherForm
from core.models import (
    Teacher,
    TeacherAssignment,
)
from core.utils.permissions import get_school_for_user, role_required


@login_required
@role_required("admin", "superuser")
def teacher_list(request):
    school = get_school_for_user(request.user)
    if not school:
        messages.error(request, "No school linked to your account.")
        return render(request, "teachers/list.html", {"teachers": [], "school": None})

    status = request.GET.get("status", "active")
    qs = Teacher.objects.filter(school=school)
    if status == "active":
        qs = qs.filter(is_active=True)
    elif status == "inactive":
        qs = qs.filter(is_active=False)

    q = request.GET.get("q", "").strip()
    if q:
        token_filter = Q()
        for token in q.split():
            token_filter &= (
                Q(first_name__icontains=token)
                | Q(last_name__icontains=token)
                | Q(teacher_code__icontains=token)
                | Q(email__icontains=token)
            )
        qs = qs.filter(token_filter)

    qs = qs.annotate(
        assignment_count=Count(
            "assignments", filter=Q(assignments__is_active=True), distinct=True
        )
    )
    qs = qs.order_by("first_name", "last_name").distinct()

    # Per-page selector (default 25)
    try:
        per_page = int(request.GET.get("per_page", 25))
    except (TypeError, ValueError):
        per_page = 25
    if per_page not in (10, 25, 50, 100):
        per_page = 25

    paginator = Paginator(qs, per_page)

    # Guard against out-of-range / malformed page numbers
    try:
        page_num = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page_num = 1
    page = paginator.get_page(page_num)

    page_qs = f"status={status}&"
    if q:
        page_qs += f"q={q}&"

    ctx = {
        "page_obj": page,
        "teachers": page.object_list,
        "query": q,
        "status": status,
        "per_page": per_page,
        "page_qs": page_qs,
        "total_count": paginator.count,
        "is_htmx": bool(request.headers.get("HX-Request")),
    }

    template = "teachers/_list_results.html" if ctx["is_htmx"] else "teachers/list.html"
    return render(request, template, ctx)


@login_required
@role_required("admin", "superuser")
def teacher_delete(request, pk):
    school = get_school_for_user(request.user)
    teacher = get_object_or_404(Teacher, pk=pk, school=school)

    if request.method == "POST":
        teacher.is_active = False
        teacher.save(update_fields=["is_active"])
        # Deactivate all assignments so the teacher stops appearing in reports.
        TeacherAssignment.objects.filter(teacher=teacher, is_active=True).update(
            is_active=False
        )
        # Deactivate any linked user account.
        profile = getattr(teacher, "user_profile", None)
        if profile and profile.user:
            profile.user.is_active = False
            profile.user.save(update_fields=["is_active"])
        messages.success(request, f"Teacher {teacher} deactivated.")
        return redirect("teacher_list")

    return render(
        request,
        "teachers/confirm_delete.html",
        {"teacher": teacher, "assignment_count": teacher.assignments.filter(is_active=True).count()},
    )


@login_required
@role_required("admin", "superuser")
def teacher_create(request):
    school = get_school_for_user(request.user)
    if not school:
        messages.error(request, "No school linked to your account.")
        return redirect("teacher_list")

    if request.method == "POST":
        form = TeacherForm(request.POST, request.FILES, school=school)
        if form.is_valid():
            teacher = form.save(commit=False)
            teacher.school = school
            teacher.save()
            messages.success(request, f"Teacher {teacher} created.")
            return redirect("teacher_detail", pk=teacher.pk)
    else:
        form = TeacherForm(school=school)

    return render(request, "teachers/create.html", {"form": form})


@login_required
def teacher_detail(request, pk):
    school = get_school_for_user(request.user)
    teacher = get_object_or_404(Teacher, pk=pk)
    if school and teacher.school_id != school.pk:
        messages.error(request, "Teacher not found.")
        return redirect("teacher_list")

    assignments = TeacherAssignment.objects.filter(
        teacher=teacher, is_active=True
    ).select_related("school_class", "subject").order_by("school_class__sort_order", "subject__sort_order")

    is_admin = False
    if request.user.is_superuser:
        is_admin = True
    elif hasattr(request.user, "profile"):
        is_admin = request.user.profile.role == "admin"

    return render(
        request,
        "teachers/detail.html",
        {
            "teacher": teacher,
            "assignments": assignments,
            "is_admin": is_admin,
        },
    )


@login_required
@role_required("admin", "superuser")
def teacher_edit(request, pk):
    school = get_school_for_user(request.user)
    if not school:
        messages.error(request, "No school linked to your account.")
        return redirect("teacher_list")
    teacher = get_object_or_404(Teacher, pk=pk, school=school)

    if request.method == "POST":
        form = TeacherForm(request.POST, request.FILES, instance=teacher, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, f"Teacher {teacher} updated.")
            return redirect("teacher_detail", pk=teacher.pk)
    else:
        form = TeacherForm(instance=teacher, school=school)

    return render(request, "teachers/edit.html", {"form": form, "teacher": teacher})


@login_required
@role_required("admin", "superuser")
def teacher_assignments(request):
    school = get_school_for_user(request.user)
    if not school:
        messages.error(request, "No school linked to your account.")
        return render(request, "teachers/assignments.html", {"assignments": [], "form": None})

    assignments = TeacherAssignment.objects.filter(
        teacher__school=school, is_active=True
    ).select_related("teacher", "school_class", "subject").order_by(
        "school_class__sort_order", "subject__sort_order"
    )

    # Per-page selector (default 25)
    try:
        per_page = int(request.GET.get("per_page", 25))
    except (TypeError, ValueError):
        per_page = 25
    if per_page not in (10, 25, 50, 100):
        per_page = 25

    if request.method == "POST":
        redirect_url = "teacher_assignments"
        if request.POST.get("page"):
            try:
                redirect_url = (
                    f"{redirect_url}?page={int(request.POST['page'])}&per_page={per_page}"
                )
            except (TypeError, ValueError):
                redirect_url = "teacher_assignments"

        if request.POST.get("action") == "delete":
            assignment_id = request.POST.get("assignment_id")
            if assignment_id:
                ta = TeacherAssignment.objects.filter(pk=assignment_id, teacher__school=school).first()
                if ta:
                    ta.is_active = False
                    ta.save()
                    messages.success(request, "Assignment removed.")
                return redirect(redirect_url)

        form = TeacherAssignmentForm(request.POST, school=school)
        if form.is_valid():
            teacher = form.cleaned_data["teacher"]
            school_class = form.cleaned_data["school_class"]
            subject = form.cleaned_data["subject"]
            is_class_master = form.cleaned_data["is_class_master"]

            existing = TeacherAssignment.objects.filter(
                teacher=teacher, school_class=school_class, subject=subject
            ).first()
            if existing:
                existing.is_active = True
                existing.is_class_master = is_class_master
                existing.save()
                messages.success(request, "Assignment updated.")
            else:
                TeacherAssignment.objects.create(
                    teacher=teacher,
                    school_class=school_class,
                    subject=subject,
                    is_class_master=is_class_master,
                )
                messages.success(request, "Assignment created.")
            return redirect(redirect_url)
    else:
        form = TeacherAssignmentForm(school=school)

    paginator = Paginator(assignments, per_page)

    # Guard against out-of-range / malformed page numbers
    try:
        page_num = int(request.GET.get("page", 1))
    except (TypeError, ValueError):
        page_num = 1
    page = paginator.get_page(page_num)

    return render(
        request,
        "teachers/assignments.html",
        {
            "page_obj": page,
            "assignments": page.object_list,
            "total_count": paginator.count,
            "per_page": per_page,
            "form": form,
        },
    )
