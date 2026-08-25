from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from core.models import SMSConfig, SMSMessage
from core.utils.notifications import process_sms_queue, queue_sms
from core.utils.permissions import get_school_for_user, role_required


@login_required
@role_required("admin", "superuser")
def sms_configuration(request):
    school = get_school_for_user(request.user)
    if not school:
        messages.error(request, "No school linked to your account.")
        return redirect("settings")

    config, _ = SMSConfig.objects.get_or_create(school=school)
    recent_messages = SMSMessage.objects.filter(config=config)[:20]
    queued_count = SMSMessage.objects.filter(config=config, status="queued").count()
    sent_today = config.messages_today()

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "save_config":
            config.provider = request.POST.get("provider", "manual")
            config.api_key = request.POST.get("api_key", "").strip()
            config.api_secret = request.POST.get("api_secret", "").strip()
            config.sender_id = request.POST.get("sender_id", "").strip()
            config.is_active = request.POST.get("is_active") == "on"
            try:
                config.daily_limit = int(request.POST.get("daily_limit", 100))
            except (TypeError, ValueError):
                config.daily_limit = 100
            config.save()
            messages.success(request, "SMS configuration saved.")
            return redirect("sms_configuration")
        elif action == "send_test":
            test_number = request.POST.get("test_number", "").strip()
            if not test_number:
                messages.error(request, "Enter a test phone number.")
                return redirect("sms_configuration")
            sms = queue_sms(
                config=config,
                recipient_number=test_number,
                message="Test message from School Management System.",
                user=request.user,
            )
            messages.success(request, f"Test SMS queued ({sms.pk}).")
            return redirect("sms_configuration")
        elif action == "process_queue":
            sent, failed = process_sms_queue()
            messages.success(
                request, f"Queue processed: {sent} sent, {failed} failed."
            )
            return redirect("sms_configuration")

    return render(
        request,
        "settings/sms_config.html",
        {
            "config": config,
            "recent_messages": recent_messages,
            "queued_count": queued_count,
            "sent_today": sent_today,
        },
    )


@login_required
@role_required("admin", "superuser")
def sms_history(request):
    school = get_school_for_user(request.user)
    if not school:
        return redirect("settings")

    config = SMSConfig.objects.filter(school=school).first()
    if not config:
        messages.error(request, "Configure SMS first.")
        return redirect("sms_configuration")

    messages_qs = SMSMessage.objects.filter(config=config)

    status_filter = request.GET.get("status")
    if status_filter:
        messages_qs = messages_qs.filter(status=status_filter)

    return render(
        request,
        "settings/sms_history.html",
        {
            "messages_list": messages_qs[:100],
            "status_filter": status_filter or "",
        },
    )


@login_required
@role_required("admin", "superuser")
def sms_cancel(request, sms_id):
    sms = get_object_or_404(SMSMessage, pk=sms_id, status="queued")
    sms.status = "cancelled"
    sms.save(update_fields=["status"])
    messages.success(request, "SMS cancelled.")
    return redirect("sms_history")
