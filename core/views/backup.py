import json
import os
import platform
import uuid
from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render

from core.models import License, School
from core.utils.backup import (
    create_backup_archive,
    generate_scheduled_task_script,
    generate_scheduled_task_xml,
    restore_backup_archive,
)
from core.utils.permissions import (
    get_school_for_user,
    role_required,
    superuser_required,
)


@login_required
@superuser_required
def backup_management(request):
    from core.models.backup import BackupHistory

    school = get_school_for_user(request.user)
    backups = BackupHistory.objects.all()[:20]

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            backup_type = request.POST.get("backup_type", "full")
            notes = request.POST.get("notes", "")
            history = create_backup_archive(
                user=request.user, notes=notes, backup_type=backup_type
            )
            messages.success(
                request, f"Backup created: {history.filename} ({history.size_display})"
            )
            return redirect("backup_management")
        elif action == "restore":
            backup_id = request.POST.get("backup_id")
            success, msg = restore_backup_archive(backup_id)
            if success:
                messages.success(request, msg)
            else:
                messages.error(request, msg)
            return redirect("backup_management")
        elif action == "generate_schedule":
            generate_scheduled_task_script()
            xml = generate_scheduled_task_xml()
            messages.success(
                request,
                f"Schedule scripts generated. Import {os.path.basename(xml)} "
                f"into Windows Task Scheduler.",
            )
            return redirect("backup_management")

    return render(
        request,
        "settings/backup.html",
        {"backups": backups, "school": school},
    )


@login_required
@superuser_required
def download_backup(request, backup_id):
    from core.models.backup import BackupHistory

    backup = BackupHistory.objects.get(pk=backup_id)
    if not os.path.exists(backup.filepath):
        messages.error(request, "Backup file not found.")
        return redirect("backup_management")

    with open(backup.filepath, "rb") as f:
        response = HttpResponse(f.read(), content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="{backup.filename}"'
        return response


@login_required
@role_required("admin", "superuser")
def license_info(request):
    from core.utils.tenancy import get_tenant, get_tenant_license

    school = get_tenant(request)
    license_obj = get_tenant_license(school)
    all_licenses = (
        License.objects.filter(school=school).order_by("-expires_at")[:10]
        if school
        else License.objects.none()
    )

    machine_id = hashlib.sha256(
        (platform.node() + str(uuid.getnode())).encode()
    ).hexdigest()[:64]
    student_count = 0
    if school:
        from core.models import Student

        student_count = Student.objects.filter(school=school, is_active=True).count()

    return render(
        request,
        "settings/license_info.html",
        {
            "license": license_obj,
            "all_licenses": all_licenses,
            "machine_id": machine_id,
            "student_count": student_count,
        },
    )


import hashlib


@login_required
@superuser_required
def generate_license_key(request):
    if request.method == "POST":
        school_name = request.POST.get("school_name", "").strip()
        max_students = int(request.POST.get("max_students", 500))
        max_devices = int(request.POST.get("max_devices", 3))
        validity_days = int(request.POST.get("validity_days", 365))

        if not school_name:
            messages.error(request, "School name is required.")
            return redirect("generate_license_key")

        expires = date.today() + timedelta(days=validity_days)
        payload = {
            "school": school_name,
            "max_students": max_students,
            "max_devices": max_devices,
            "expires": expires.isoformat(),
        }

        import base64

        raw = (
            base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True).encode())
            .rstrip(b"=")
            .decode()
        )

        sig = hashlib.new(
            "sha256",
            json.dumps(payload, sort_keys=True).encode(),
            usedforsecurity=False,
        ).hexdigest()[:16]

        product_key = f"OC-{sig}-{raw}"

        return render(
            request,
            "settings/license_generated.html",
            {
                "product_key": product_key,
                "school_name": school_name,
                "expires": expires,
                "max_students": max_students,
                "max_devices": max_devices,
            },
        )

    return render(request, "settings/generate_license.html")


@login_required
@role_required("admin", "superuser")
def offline_license_check(request):
    """Check license validity offline using stored validation."""
    from core.utils.tenancy import get_tenant

    school = get_tenant(request)
    license_obj = (
        License.objects.filter(school=school).order_by("-expires_at").first()
        if school
        else None
    )
    machine_id = hashlib.sha256(
        (platform.node() + str(uuid.getnode())).encode()
    ).hexdigest()[:64]

    is_valid_offline = False
    validation_message = ""

    if license_obj:
        if license_obj.status == "revoked":
            validation_message = "License has been revoked."
        elif license_obj.expires_at < date.today():
            validation_message = (
                f"License expired on {license_obj.expires_at.strftime('%B %d, %Y')}."
            )
        elif license_obj.machine_id and license_obj.machine_id != machine_id:
            validation_message = (
                "License bound to a different machine. " "Contact support to transfer."
            )
        elif (
            license_obj.activation_count > license_obj.max_devices
            and machine_id not in (license_obj.machine_id or "")
        ):
            validation_message = f"Device limit ({license_obj.max_devices}) reached."
        else:
            is_valid_offline = True
            validation_message = "License is valid offline."
    else:
        validation_message = "No license found. Please activate."

    return render(
        request,
        "settings/offline_license.html",
        {
            "license": license_obj,
            "machine_id": machine_id,
            "is_valid": is_valid_offline,
            "validation_message": validation_message,
        },
    )
