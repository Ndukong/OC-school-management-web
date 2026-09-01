import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import IntegrityError, models, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from core.forms import (
    AcademicTermForm,
    ClassSubjectForm,
    CompetencyForm,
    FeeTypeForm,
    PTARubricHeadForm,
    PTARubricSubHeadForm,
    SchoolClassForm,
    SchoolForm,
    SubjectForm,
    UserCreateForm,
    UserEditForm,
)
from core.models import (
    AcademicTerm,
    ClassSubject,
    Competency,
    FeeType,
    PTADueConfig,
    PTARubricHead,
    PTARubricSubHead,
    SchoolClass,
    Subject,
    Teacher,
    UserProfile,
)
from core.utils.permissions import get_school_for_user, role_required


def _require_school(request):
    """Return the current admin's school, or None after flashing an error."""
    school = get_school_for_user(request.user)
    if not school:
        messages.error(request, "No school linked to your account.")
    return school


@login_required
@role_required("admin", "superuser")
def settings_hub(request):
    school = _require_school(request)
    counts = {}
    if school:
        counts = {
            "classes": SchoolClass.objects.filter(school=school).count(),
            "subjects": Subject.objects.filter(school=school).count(),
            "class_subjects": ClassSubject.objects.filter(
                school_class__school=school
            ).count(),
            "terms": AcademicTerm.objects.filter(school=school).count(),
            "competencies": Competency.objects.filter(subject__school=school).count(),
            "users": UserProfile.objects.filter(school=school).count(),
            "pta_heads": PTARubricHead.objects.filter(school=school).count(),
            "pta_dues": PTADueConfig.objects.filter(school=school).count(),
            "fee_types": FeeType.objects.filter(school=school).count(),
            "teachers": Teacher.objects.filter(school=school, is_active=True).count(),
        }

    config_cards = [
        {
            "url": reverse("school_profile"),
            "icon": "&#127970;",
            "title": "School Profile",
            "desc": "Name, matricule, contact, bilingual letterhead, logo & seal.",
            "count": None,
        },
        {
            "url": reverse("terms_manage"),
            "icon": "&#128197;",
            "title": "Academic Terms",
            "desc": "Create terms and set the current one.",
            "count": counts.get("terms"),
        },
        {
            "url": reverse("classes_manage"),
            "icon": "&#127891;",
            "title": "Classes & Streams",
            "desc": "Forms, streams, cycles and promotion marks.",
            "count": counts.get("classes"),
        },
        {
            "url": reverse("subjects_manage"),
            "icon": "&#128221;",
            "title": "Subjects",
            "desc": "Subject catalogue for the school.",
            "count": counts.get("subjects"),
        },
        {
            "url": reverse("class_subjects_all"),
            "icon": "&#10133;",
            "title": "Class Subjects & Coefficients",
            "desc": "Assign subjects to each class with coefficients.",
            "count": counts.get("class_subjects"),
        },
        {
            "url": reverse("competencies_manage"),
            "icon": "&#10004;",
            "title": "Competencies",
            "desc": "Competencies by subject, term and form level.",
            "count": counts.get("competencies"),
        },
        {
            "url": reverse("users_manage"),
            "icon": "&#128101;",
            "title": "Users & Teacher Links",
            "desc": "Accounts, roles and teacher links.",
            "count": counts.get("users"),
        },
        {
            "url": reverse("pta_config"),
            "icon": "&#8355;",
            "title": "PTA Configuration",
            "desc": "Rubric heads, sub-heads, dues and fee types.",
            "count": counts.get("pta_heads") or counts.get("fee_types"),
        },
        {
            "url": reverse("conduct_config"),
            "icon": "&#9888;",
            "title": "Conduct Thresholds",
            "desc": "Discipline levels for the class council.",
            "count": None,
        },
        {
            "url": reverse("audit_log"),
            "icon": "&#128220;",
            "title": "Audit Trail",
            "desc": "Logins and every tracked change, newest first.",
            "count": None,
        },
    ]

    return render(
        request,
        "settings/hub.html",
        {"school": school, "counts": counts, "config_cards": config_cards},
    )


@login_required
@role_required("admin", "superuser")
def school_profile(request):
    school = _require_school(request)
    if not school:
        return redirect("settings")

    if request.method == "POST":
        form = SchoolForm(request.POST, request.FILES, instance=school)
        if form.is_valid():
            form.save()
            messages.success(request, "School profile saved.")
            return redirect("school_profile")
    else:
        form = SchoolForm(instance=school)

    return render(
        request,
        "settings/school_profile.html",
        {"form": form, "school": school},
    )


@login_required
@role_required("admin", "superuser")
def terms_manage(request):
    school = _require_school(request)
    if not school:
        return redirect("settings")

    terms = AcademicTerm.objects.filter(school=school).order_by(
        "-year_start", "term_number"
    )

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            form = AcademicTermForm(request.POST, school=school)
            if form.is_valid():
                term = form.save(commit=False)
                term.school = school
                term.save()
                if term.is_current:
                    AcademicTerm.objects.filter(school=school).exclude(
                        pk=term.pk
                    ).update(is_current=False)
                messages.success(request, f"Term {term} created.")
                return redirect("terms_manage")
            messages.error(request, form.errors.as_text())
            return redirect("terms_manage")
        elif action == "set_current":
            term_id = request.POST.get("term_id")
            term = get_object_or_404(AcademicTerm, pk=term_id, school=school)
            AcademicTerm.objects.filter(school=school).update(is_current=False)
            term.is_current = True
            term.save(update_fields=["is_current"])
            messages.success(request, f"{term} set as current term.")
            return redirect("terms_manage")
        elif action == "delete":
            term_id = request.POST.get("term_id")
            term = get_object_or_404(AcademicTerm, pk=term_id, school=school)
            term.delete()
            messages.success(request, "Term deleted.")
            return redirect("terms_manage")

    return render(
        request,
        "settings/terms.html",
        {"terms": terms, "form": AcademicTermForm(school=school)},
    )


@login_required
@role_required("admin", "superuser")
def classes_manage(request):
    school = _require_school(request)
    if not school:
        return redirect("settings")

    classes = SchoolClass.objects.filter(school=school).order_by("sort_order", "code")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            form = SchoolClassForm(request.POST, school=school)
            if form.is_valid():
                cls = form.save(commit=False)
                cls.school = school
                try:
                    cls.save()
                except IntegrityError:
                    messages.error(
                        request,
                        f"A class with code '{cls.code}' already exists for this school.",
                    )
                    return redirect("classes_manage")
                messages.success(request, f"Class {cls} created.")
                return redirect("classes_manage")
            messages.error(request, form.errors.as_text())
            return redirect("classes_manage")
        elif action == "delete":
            class_id = request.POST.get("class_id")
            cls = get_object_or_404(SchoolClass, pk=class_id, school=school)
            if cls.enrollments.exists():
                messages.error(
                    request,
                    f"Cannot delete {cls}: students are enrolled in this class.",
                )
            else:
                cls.delete()
                messages.success(request, "Class deleted.")
            return redirect("classes_manage")

    return render(
        request,
        "settings/classes.html",
        {"classes": classes, "form": SchoolClassForm(school=school)},
    )


@login_required
@role_required("admin", "superuser")
def subjects_manage(request):
    school = _require_school(request)
    if not school:
        return redirect("settings")

    subjects = Subject.objects.filter(school=school).order_by("sort_order", "name")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            form = SubjectForm(request.POST, school=school)
            if form.is_valid():
                subj = form.save(commit=False)
                subj.school = school
                try:
                    subj.save()
                except IntegrityError:
                    messages.error(
                        request,
                        f"A subject with code '{subj.code}' already exists for this school.",
                    )
                    return redirect("subjects_manage")
                messages.success(request, f"Subject {subj} created.")
                return redirect("subjects_manage")
            messages.error(request, form.errors.as_text())
            return redirect("subjects_manage")
        elif action == "delete":
            subject_id = request.POST.get("subject_id")
            subject = get_object_or_404(Subject, pk=subject_id, school=school)
            subject.delete()
            messages.success(request, "Subject deleted.")
            return redirect("subjects_manage")

    return render(
        request,
        "settings/subjects.html",
        {"subjects": subjects, "form": SubjectForm(school=school)},
    )


@login_required
@role_required("admin", "superuser")
def class_subjects_index(request):
    school = _require_school(request)
    if not school:
        return redirect("settings")

    classes = (
        SchoolClass.objects.filter(school=school)
        .annotate(subject_count=models.Count("subjects"))
        .order_by("sort_order", "code")
    )
    return render(
        request,
        "settings/class_subjects_index.html",
        {"classes": classes},
    )


@login_required
@role_required("admin", "superuser")
def class_subjects_manage(request, class_id):
    school = _require_school(request)
    if not school:
        return redirect("settings")

    school_class = get_object_or_404(SchoolClass, pk=class_id, school=school)
    items = ClassSubject.objects.filter(school_class=school_class).select_related(
        "subject"
    )

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add":
            post_data = request.POST.copy()
            post_data["school_class"] = school_class.pk
            form = ClassSubjectForm(post_data, school=school)
            if form.is_valid():
                subject = form.cleaned_data["subject"]
                coefficient = form.cleaned_data["coefficient"]
                sort_order = form.cleaned_data.get("sort_order") or 0
                _, created = ClassSubject.objects.get_or_create(
                    school_class=school_class,
                    subject=subject,
                    defaults={
                        "coefficient": coefficient,
                        "sort_order": sort_order,
                    },
                )
                if not created:
                    ClassSubject.objects.filter(
                        school_class=school_class, subject=subject
                    ).update(coefficient=coefficient, sort_order=sort_order)
                    messages.success(request, "Subject coefficient updated.")
                else:
                    messages.success(request, "Subject added to class.")
                return redirect("class_subjects_manage", class_id=school_class.pk)
            messages.error(request, form.errors.as_text())
            return redirect("class_subjects_manage", class_id=school_class.pk)
        elif action == "update":
            cs_id = request.POST.get("cs_id")
            coefficient = request.POST.get("coefficient")
            item = get_object_or_404(ClassSubject, pk=cs_id, school_class=school_class)
            try:
                coeff = int(coefficient)
                if coeff < 1:
                    raise ValueError
                item.coefficient = coeff
                item.save()
                messages.success(request, "Coefficient updated.")
            except (TypeError, ValueError):
                messages.error(request, "Coefficient must be a positive integer.")
            return redirect("class_subjects_manage", class_id=school_class.pk)
        elif action == "delete":
            cs_id = request.POST.get("cs_id")
            item = get_object_or_404(ClassSubject, pk=cs_id, school_class=school_class)
            item.delete()
            messages.success(request, "Subject removed from class.")
            return redirect("class_subjects_manage", class_id=school_class.pk)

    return render(
        request,
        "settings/class_subjects.html",
        {
            "school_class": school_class,
            "items": items,
            "form": ClassSubjectForm(school=school),
        },
    )


@login_required
@role_required("admin", "superuser")
def competencies_manage(request):
    school = _require_school(request)
    if not school:
        return redirect("settings")

    subjects = Subject.objects.filter(school=school).order_by("sort_order", "name")
    terms = AcademicTerm.objects.filter(school=school).order_by(
        "-year_start", "term_number"
    )

    subject_id = request.GET.get("subject_id")
    term_id = request.GET.get("term_id")
    form_level = request.GET.get("form_level", "")

    qs = Competency.objects.filter(subject__school=school).select_related(
        "subject", "term"
    )
    if subject_id:
        qs = qs.filter(subject_id=subject_id)
    if term_id:
        qs = qs.filter(term_id=term_id)
    if form_level:
        try:
            qs = qs.filter(form_level=int(form_level))
        except (TypeError, ValueError):
            pass
    competencies = qs.order_by("subject__sort_order", "form_level", "sort_order")

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            form = CompetencyForm(request.POST, school=school)
            if form.is_valid():
                competency = form.save(commit=False)
                competency.save()
                messages.success(request, "Competency added.")
                return redirect("competencies_manage")
            messages.error(request, form.errors.as_text())
            return redirect("competencies_manage")
        elif action == "delete":
            comp_id = request.POST.get("competency_id")
            competency = get_object_or_404(
                Competency, pk=comp_id, subject__school=school
            )
            competency.delete()
            messages.success(request, "Competency deleted.")
            return redirect("competencies_manage")

    return render(
        request,
        "settings/competencies.html",
        {
            "subjects": subjects,
            "terms": terms,
            "competencies": competencies,
            "form": CompetencyForm(school=school),
            "subject_id": subject_id or "",
            "term_id": term_id or "",
            "form_level": form_level,
        },
    )


@login_required
@role_required("admin", "superuser")
def users_manage(request):
    school = _require_school(request)
    if not school:
        return redirect("settings")

    profiles = UserProfile.objects.filter(school=school).select_related(
        "user", "teacher"
    )

    create_form = UserCreateForm(school=school)
    edit_form = None

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            create_form = UserCreateForm(request.POST, school=school)
            if create_form.is_valid():
                with transaction.atomic():
                    user = User.objects.create_user(
                        username=create_form.cleaned_data["username"],
                        password=create_form.cleaned_data["password"],
                        first_name=create_form.cleaned_data["first_name"],
                        last_name=create_form.cleaned_data["last_name"],
                        email=create_form.cleaned_data["email"],
                        is_staff=False,
                    )
                    UserProfile.objects.create(
                        user=user,
                        school=school,
                        role=create_form.cleaned_data["role"],
                        teacher=create_form.cleaned_data["teacher"],
                    )
                messages.success(request, f"User {user.username} created.")
                return redirect("users_manage")
            messages.error(request, create_form.errors.as_text())
            return redirect("users_manage")
        elif action == "update":
            profile_id = request.POST.get("profile_id")
            profile = get_object_or_404(UserProfile, pk=profile_id, school=school)
            edit_form = UserEditForm(request.POST, instance=profile, school=school)
            if edit_form.is_valid():
                edit_form.save()
                profile.user.first_name = edit_form.cleaned_data.get("first_name", "")
                profile.user.last_name = edit_form.cleaned_data.get("last_name", "")
                profile.user.email = edit_form.cleaned_data.get("email", "")
                profile.user.is_active = edit_form.cleaned_data.get("is_active", True)
                profile.user.save()
                messages.success(request, f"User {profile.user.username} updated.")
                return redirect("users_manage")
            messages.error(request, edit_form.errors.as_text())
            return redirect("users_manage")
        elif action == "reset_password":
            profile_id = request.POST.get("profile_id")
            password = request.POST.get("password", "")
            profile = get_object_or_404(UserProfile, pk=profile_id, school=school)
            if len(password) < 6:
                messages.error(request, "Password must be at least 6 characters.")
                return redirect("users_manage")
            profile.user.set_password(password)
            profile.user.save()
            messages.success(request, f"Password reset for {profile.user.username}.")
            return redirect("users_manage")

    return render(
        request,
        "settings/users.html",
        {
            "profiles": profiles,
            "teachers": Teacher.objects.filter(school=school, is_active=True).order_by(
                "first_name", "last_name"
            ),
            "create_form": create_form,
            "edit_form": edit_form,
        },
    )


@login_required
@role_required("admin", "superuser")
def pta_config(request):
    school = _require_school(request)
    if not school:
        return redirect("settings")

    heads = PTARubricHead.objects.filter(school=school).order_by("sort_order")
    sub_heads = PTARubricSubHead.objects.filter(
        rubric_head__school=school
    ).select_related("rubric_head")
    due_configs = PTADueConfig.objects.filter(school=school).select_related(
        "school_class"
    )
    fee_types = FeeType.objects.filter(school=school)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "add_head":
            form = PTARubricHeadForm(request.POST, school=school)
            if form.is_valid():
                head = form.save(commit=False)
                head.school = school
                head.save()
                messages.success(request, f"Rubric head {head.name} created.")
            else:
                messages.error(request, form.errors.as_text())
            return redirect("pta_config")
        elif action == "delete_head":
            head_id = request.POST.get("head_id")
            head = get_object_or_404(PTARubricHead, pk=head_id, school=school)
            head.delete()
            messages.success(request, "Rubric head deleted.")
            return redirect("pta_config")
        elif action == "add_subhead":
            form = PTARubricSubHeadForm(request.POST, school=school)
            if form.is_valid():
                PTARubricSubHead.objects.create(
                    rubric_head=form.cleaned_data["rubric_head"],
                    name=form.cleaned_data["name"],
                    code=form.cleaned_data.get("code", ""),
                )
                messages.success(request, "Sub-head created.")
            else:
                messages.error(request, form.errors.as_text())
            return redirect("pta_config")
        elif action == "delete_subhead":
            sub_id = request.POST.get("sub_id")
            sub = get_object_or_404(
                PTARubricSubHead, pk=sub_id, rubric_head__school=school
            )
            sub.delete()
            messages.success(request, "Sub-head deleted.")
            return redirect("pta_config")
        elif action == "save_dues":
            for sc in SchoolClass.objects.filter(school=school):
                amount = request.POST.get(f"due_{sc.pk}")
                if amount is None or amount == "":
                    continue
                try:
                    from decimal import Decimal, InvalidOperation

                    value = Decimal(amount)
                    if value < 0:
                        raise InvalidOperation
                except (InvalidOperation, TypeError):
                    messages.error(request, f"Invalid amount for {sc}.")
                    continue
                PTADueConfig.objects.update_or_create(
                    school=school,
                    school_class=sc,
                    defaults={"amount": value},
                )
            messages.success(request, "PTA dues saved.")
            return redirect("pta_config")
        elif action == "add_feetype":
            form = FeeTypeForm(request.POST, school=school)
            if form.is_valid():
                ft = form.save(commit=False)
                ft.school = school
                ft.save()
                messages.success(request, f"Fee type {ft.name} created.")
            else:
                messages.error(request, form.errors.as_text())
            return redirect("pta_config")
        elif action == "delete_feetype":
            ft_id = request.POST.get("feetype_id")
            ft = get_object_or_404(FeeType, pk=ft_id, school=school)
            ft.delete()
            messages.success(request, "Fee type deleted.")
            return redirect("pta_config")

    return render(
        request,
        "settings/pta_config.html",
        {
            "heads": heads,
            "sub_heads": sub_heads,
            "due_configs": {dc.school_class_id: dc.amount for dc in due_configs},
            "classes": SchoolClass.objects.filter(school=school).order_by(
                "sort_order", "code"
            ),
            "fee_types": fee_types,
            "head_form": PTARubricHeadForm(school=school),
            "subhead_form": PTARubricSubHeadForm(school=school),
            "feetype_form": FeeTypeForm(school=school),
        },
    )


@login_required
@role_required("admin", "superuser")
def audit_log(request):
    from auditlog.models import LogEntry

    entries = LogEntry.objects.select_related("actor", "content_type").order_by(
        "-timestamp"
    )[:200]
    rows = []
    for entry in entries:
        changes = entry.changes
        if isinstance(changes, str):
            try:
                changes = json.loads(changes)
            except json.JSONDecodeError:
                changes = {}
        if not isinstance(changes, dict):
            changes = {}
        if "auth_event" in changes:
            event = changes["auth_event"]
            detail = event.get("value", "") if isinstance(event, dict) else str(event)
        elif changes:
            detail = ", ".join(str(key) for key in changes)
        else:
            detail = ""
        rows.append(
            {
                "timestamp": entry.timestamp,
                "actor": entry.actor.username if entry.actor else "-",
                "action": entry.get_action_display(),
                "object": entry.object_repr,
                "detail": detail,
                "ip": entry.remote_addr,
            }
        )
    return render(request, "settings/audit.html", {"rows": rows})
