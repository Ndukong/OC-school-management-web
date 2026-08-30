"""Cache-backed brute-force throttling shared by staff and parent logins.

Counters and lockouts live in the Django cache rather than the session, so
clearing browser cookies no longer resets an attacker's attempt counter.
With the default per-process LocMemCache the limit applies per server
process, which is exact for the single-process offline runserver deployment
and still a hard curb for small gunicorn deployments.
"""

from datetime import timedelta

from django.core.cache import cache
from django.utils import timezone


def client_ip(request) -> str:
    """Return the client IP, honouring the proxy header set by Railway."""
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


class BruteForceThrottle:
    """Track failed attempts per scope (username, IP, unique_id...) in cache.

    A lockout on ANY scope blocks the request. Failure counters expire after
    the scope's lockout window, so "N failures within the window" is what
    triggers the lock.
    """

    def __init__(self, namespace: str):
        self.namespace = namespace

    def _fails_key(self, scope: str, key: str) -> str:
        return f"{self.namespace}:fails:{scope}:{key}"

    def _lock_key(self, scope: str, key: str) -> str:
        return f"{self.namespace}:lock:{scope}:{key}"

    def check(self, entries) -> tuple[int | None, int]:
        """Return (lockout_minutes_or_None, attempts_remaining).

        ``entries`` is an iterable of ``(scope, key, max_attempts,
        lockout_minutes)`` tuples; the last element is ignored here.
        """
        now = timezone.now().timestamp()
        lock_until = 0.0
        remaining: int | None = None
        for scope, key, max_attempts, _lockout_minutes in entries:
            until = cache.get(self._lock_key(scope, key))
            if until:
                lock_until = max(lock_until, until)
                continue
            fails = cache.get(self._fails_key(scope, key), 0)
            left = max(0, max_attempts - fails)
            remaining = left if remaining is None else min(remaining, left)
        if lock_until > now:
            return max(1, int((lock_until - now) // 60) or 1), 0
        return None, (remaining if remaining is not None else 0)

    def record_failure(self, entries) -> None:
        """Record one failed attempt for every ``(scope, key, max, minutes)``."""
        now = timezone.now()
        for scope, key, max_attempts, lockout_minutes in entries:
            fails_key = self._fails_key(scope, key)
            fails = cache.get(fails_key, 0) + 1
            if fails >= max_attempts:
                until = now + timedelta(minutes=lockout_minutes)
                cache.set(
                    self._lock_key(scope, key),
                    until.timestamp(),
                    timeout=lockout_minutes * 60 + 60,
                )
                cache.delete(fails_key)
            else:
                cache.set(fails_key, fails, timeout=lockout_minutes * 60)

    def reset(self, entries) -> None:
        """Clear counters and lockouts for the given scopes."""
        for scope, key, *_ in entries:
            cache.delete(self._fails_key(scope, key))
            cache.delete(self._lock_key(scope, key))
