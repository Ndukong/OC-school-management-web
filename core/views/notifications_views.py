from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from core.models import Notification


@login_required
def notifications_list(request):
    notifications = Notification.objects.filter(recipient=request.user)[:50]
    unread_count = Notification.objects.filter(
        recipient=request.user, is_read=False
    ).count()
    return render(
        request,
        "settings/notifications.html",
        {
            "notifications": notifications,
            "unread_count": unread_count,
        },
    )


@login_required
def mark_notification_read(request, notification_id):
    notif = get_object_or_404(
        Notification, pk=notification_id, recipient=request.user
    )
    notif.mark_read()
    if request.headers.get("Accept") == "application/json":
        return JsonResponse({"ok": True})
    return redirect("notifications_list")


@login_required
def mark_all_read(request):
    Notification.objects.filter(recipient=request.user, is_read=False).update(
        is_read=True
    )
    if request.headers.get("Accept") == "application/json":
        return JsonResponse({"ok": True})
    return redirect("notifications_list")


@login_required
def notifications_unread_count(request):
    count = Notification.objects.filter(
        recipient=request.user, is_read=False
    ).count()
    return JsonResponse({"count": count})
