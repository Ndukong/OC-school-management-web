from core.models import Notification, SMSMessage


def queue_sms(config, recipient_number, message, recipient_name="", user=None):
    """Queue an SMS message for delivery."""
    sms = SMSMessage.objects.create(
        config=config,
        recipient_number=recipient_number,
        recipient_name=recipient_name,
        message=message,
        status="queued",
        created_by=user,
    )
    return sms


def process_sms_queue():
    """Process queued SMS messages. Returns (sent_count, failed_count)."""
    from django.utils import timezone

    queued = SMSMessage.objects.filter(status="queued").select_related("config")
    sent_count = 0
    failed_count = 0

    for sms in queued:
        sms.status = "sending"
        sms.save(update_fields=["status"])

        try:
            success = _send_sms(sms)
            if success:
                sms.status = "sent"
                sms.sent_at = timezone.now()
                sms.save(update_fields=["status", "sent_at"])
                sent_count += 1
            else:
                sms.retry_count += 1
                if sms.retry_count >= sms.max_retries:
                    sms.status = "failed"
                    sms.save(update_fields=["status", "retry_count", "error_message"])
                    failed_count += 1
                else:
                    sms.status = "queued"
                    sms.save(update_fields=["status", "retry_count"])
        except Exception as e:
            sms.retry_count += 1
            sms.error_message = str(e)
            if sms.retry_count >= sms.max_retries:
                sms.status = "failed"
                sms.save(update_fields=["status", "retry_count", "error_message"])
                failed_count += 1
            else:
                sms.status = "queued"
                sms.save(update_fields=["status", "retry_count", "error_message"])

    return sent_count, failed_count


def _send_sms(sms):
    """Send an SMS via the configured provider. Returns True on success."""
    config = sms.config

    if config.provider == "manual":
        return True

    if config.provider == "twilio":
        return _send_twilio(sms, config)

    if config.provider == "africastalking":
        return _send_africastalking(sms, config)

    return False


def _send_twilio(sms, config):
    try:
        import base64
        from urllib.parse import urlencode
        from urllib.request import Request, urlopen

        account_sid = config.api_key
        auth_token = config.api_secret
        from_number = config.sender_id

        if not all([account_sid, auth_token, from_number]):
            sms.error_message = "Twilio credentials not configured"
            return False

        url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
        data = urlencode(
            {"To": sms.recipient_number, "From": from_number, "Body": sms.message}
        ).encode()

        credentials = base64.b64encode(f"{account_sid}:{auth_token}".encode()).decode()

        req = Request(url, data=data, method="POST")
        req.add_header("Authorization", f"Basic {credentials}")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        with urlopen(req, timeout=30) as response:
            return response.status == 201
    except Exception as e:
        sms.error_message = f"Twilio error: {e}"
        return False


def _send_africastalking(sms, config):
    try:
        import json
        from urllib.parse import urlencode
        from urllib.request import Request, urlopen

        api_key = config.api_key
        username = config.api_secret
        from_number = config.sender_id

        if not all([api_key, username, from_number]):
            sms.error_message = "Africa's Talking credentials not configured"
            return False

        url = "https://api.africastalking.com/version1/messaging"
        data = urlencode(
            {
                "username": username,
                "to": sms.recipient_number,
                "message": sms.message,
                "from": from_number,
            }
        ).encode()

        req = Request(url, data=data, method="POST")
        req.add_header("apikey", api_key)
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        with urlopen(req, timeout=30) as response:
            result = json.loads(response.read())
            return (
                result.get("SMSMessageData", {})
                .get("Recipients", [{}])[0]
                .get("status")
                == "Success"
            )
    except Exception as e:
        sms.error_message = f"Africa's Talking error: {e}"
        return False


def send_absence_notification(student, absence_count, term, user=None):
    school = student.school
    config = getattr(school, "sms_config", None)

    message = (
        f"Dear Guardian, {student.first_name} {student.other_names or ''} "
        f"has {absence_count} unjustified absence(s) this term. "
        f"Please contact the school. - {school.name_en}"
    )

    if config and config.is_active and student.guardian_contact:
        queue_sms(
            config=config,
            recipient_number=student.guardian_contact,
            message=message,
            recipient_name=student.guardian_name,
            user=user,
        )

    from django.contrib.auth.models import User

    admins = User.objects.filter(
        profile__school=school, profile__role__in=["admin", "class_master"]
    )
    for admin in admins:
        Notification.objects.create(
            recipient=admin,
            notification_type="absence",
            title=f"Absence Alert: {student.first_name}",
            message=f"{student.first_name} has {absence_count} unjustified absence(s).",
            priority="high",
            metadata={"student_id": student.pk},
        )


def send_fee_reminder(student, amount_due, term, user=None):
    school = student.school
    config = getattr(school, "sms_config", None)

    message = (
        f"Dear Guardian, {amount_due:,.0f} FCFA is due for "
        f"{student.first_name} {student.other_names or ''} for {term}. "
        f"Please pay at the bursary. - {school.name_en}"
    )

    if config and config.is_active and student.guardian_contact:
        queue_sms(
            config=config,
            recipient_number=student.guardian_contact,
            message=message,
            recipient_name=student.guardian_name,
            user=user,
        )

    from django.contrib.auth.models import User

    admins = User.objects.filter(
        profile__school=school, profile__role__in=["admin", "bursar"]
    )
    for admin in admins:
        Notification.objects.create(
            recipient=admin,
            notification_type="fee_reminder",
            title=f"Fee Reminder: {student.first_name}",
            message=f"{amount_due:,.0f} FCFA due for {student.first_name}.",
            priority="normal",
            metadata={"student_id": student.pk},
        )


def send_report_ready_notification(student, term, user=None):
    school = student.school

    from django.contrib.auth.models import User

    admins = User.objects.filter(
        profile__school=school, profile__role__in=["admin", "class_master"]
    )
    for admin in admins:
        Notification.objects.create(
            recipient=admin,
            notification_type="report_ready",
            title=f"Report Ready: {student.first_name}",
            message=f"Report card for {student.first_name} ({term}) is ready.",
            priority="normal",
            metadata={"student_id": student.pk},
        )

    config = getattr(school, "sms_config", None)
    if config and config.is_active and student.guardian_contact:
        message = (
            f"Dear Guardian, the report card for "
            f"{student.first_name} {student.other_names or ''} is ready. "
            f"Please collect from the school. - {school.name_en}"
        )
        queue_sms(
            config=config,
            recipient_number=student.guardian_contact,
            message=message,
            recipient_name=student.guardian_name,
            user=user,
        )
