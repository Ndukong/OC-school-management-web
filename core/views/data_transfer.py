import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render

from core.utils.permissions import get_school_for_user, role_required
from core.utils.school_export import build_school_export, restore_school_export


@login_required
@role_required("admin", "superuser")
def school_data_transfer(request):
    school = get_school_for_user(request.user)
    if not school:
        messages.error(request, "No school linked to your account.")
        return redirect("settings")
    return render(request, "settings/data_transfer.html", {"school": school})


@login_required
@role_required("admin", "superuser")
def school_data_export(request):
    school = get_school_for_user(request.user)
    if not school:
        messages.error(request, "No school linked to your account.")
        return redirect("settings")

    payload = build_school_export(school)
    response = HttpResponse(
        json.dumps(payload, indent=2), content_type="application/json"
    )
    response["Content-Disposition"] = (
        f'attachment; filename="school_export_{school.matricule}.json"'
    )
    return response


@login_required
@role_required("admin", "superuser")
def school_data_import(request):
    school = get_school_for_user(request.user)
    if not school:
        messages.error(request, "No school linked to your account.")
        return redirect("settings")

    if request.method != "POST":
        return redirect("school_data_transfer")

    upload = request.FILES.get("file")
    if upload is None:
        messages.error(request, "Choose a JSON export file to import.")
        return redirect("school_data_transfer")

    try:
        data = json.loads(upload.read().decode("utf-8"))
        counts = restore_school_export(data, school)
    except (UnicodeDecodeError, json.JSONDecodeError):
        messages.error(request, "That file is not valid JSON.")
        return redirect("school_data_transfer")
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("school_data_transfer")

    if counts.get("student_conflicts"):
        messages.warning(
            request,
            f"{counts['student_conflicts']} student(s) skipped — their IDs "
            "already exist at another school.",
        )
    if counts.get("skipped"):
        messages.warning(
            request,
            f"{counts['skipped']} record(s) skipped due to missing references.",
        )
    messages.success(
        request,
        "Import complete — "
        f"terms:{counts['terms']}, classes:{counts['classes']}, "
        f"subjects:{counts['subjects']}, teachers:{counts['teachers']}, "
        f"students:{counts['students']}, enrollments:{counts['enrollments']}.",
    )
    return redirect("school_data_transfer")
