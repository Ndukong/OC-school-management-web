"""Audit trail: tracked models and login/logout/failed-login events.

Imported from CoreConfig.ready() so the registrations and signal handlers
are always wired, whatever imports core.models first.
"""

from auditlog.models import LogEntry
from auditlog.registry import auditlog
from django.contrib.auth import get_user_model, signals as auth_signals

from core.models import (
    AcademicTerm,
    AttendanceRecord,
    AttendanceRegister,
    ClassSubject,
    Competency,
    DisciplineSummary,
    ExpenditureRecord,
    FeeType,
    FinanceSummary,
    IncomeRecord,
    License,
    PTADueConfig,
    School,
    SchoolClass,
    SMSConfig,
    SMSMessage,
    Student,
    Subject,
    Teacher,
    TeacherAssignment,
    UserProfile,
)

TRACKED_MODELS = [
    School,
    AcademicTerm,
    SchoolClass,
    ClassSubject,
    Subject,
    Competency,
    Student,
    Teacher,
    TeacherAssignment,
    UserProfile,
    IncomeRecord,
    ExpenditureRecord,
    FinanceSummary,
    PTADueConfig,
    FeeType,
    DisciplineSummary,
    AttendanceRegister,
    AttendanceRecord,
    License,
    SMSConfig,
    SMSMessage,
]


def register_models() -> None:
    user_model = get_user_model()
    for model in [*TRACKED_MODELS, user_model]:
        if not auditlog.contains(model):
            auditlog.register(model)


def _client_ip(request) -> str:
    if request is None:
        return ""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def _log_auth_event(user, event: str, request=None) -> None:
    kwargs = {
        "actor": user,
        "action": LogEntry.Action.UPDATE,
        "force_log": True,
        "changes": {"auth_event": {"type": "str", "value": event}},
    }
    ip = _client_ip(request)
    if ip:
        kwargs["remote_addr"] = ip
    LogEntry.objects.log_create(user, **kwargs)


def log_login(sender, request, user, **kwargs) -> None:
    if user and user.is_authenticated:
        _log_auth_event(user, "logged in", request)


def log_logout(sender, request, user, **kwargs) -> None:
    if user and user.is_authenticated:
        _log_auth_event(user, "logged out", request)


def log_failed_login(sender, credentials, **kwargs) -> None:
    username = ((credentials or {}).get("username") or "").strip()
    if not username:
        return
    user = get_user_model().objects.filter(username__iexact=username).first()
    if not user:
        return
    _log_auth_event(user, "failed login", None)


def connect_signals() -> None:
    auth_signals.user_logged_in.connect(log_login)
    auth_signals.user_logged_out.connect(log_logout)
    auth_signals.user_login_failed.connect(log_failed_login)


def setup() -> None:
    register_models()
    connect_signals()
