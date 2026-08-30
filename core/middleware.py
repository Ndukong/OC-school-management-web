from django.http import HttpResponseForbidden


class LicenseGateMiddleware:
    """Block staff of schools whose license has lapsed from every deep URL.

    The dashboard already gates on a valid license; this closes the bypass
    via marks, finance, reports, exports and the JSON API. Runs in
    ``process_view`` so URL resolution is available for precise exemptions.
    Superusers (the platform owner) are exempt, as are the login/logout,
    activation wizard, parent portal, Django admin and static/media routes.
    """

    EXEMPT_URL_NAMES = frozenset({"login", "logout", "activate"})
    EXEMPT_NAMESPACES = frozenset({"admin", "parent"})
    EXEMPT_PREFIXES = ("/static/", "/media/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated or user.is_superuser:
            return None
        if request.path.startswith(self.EXEMPT_PREFIXES):
            return None

        match = getattr(request, "resolver_match", None)
        if match is None:
            return None
        if match.namespace in self.EXEMPT_NAMESPACES:
            return None
        if match.url_name in self.EXEMPT_URL_NAMES:
            return None

        from core.utils.permissions import get_school_for_user
        from core.utils.tenancy import license_lapsed

        school = get_school_for_user(user)
        if school is not None and license_lapsed(school):
            from django.contrib import messages
            from django.shortcuts import redirect

            messages.error(
                request,
                "Your school's license has expired or been revoked. "
                "Please contact the platform provider to renew.",
            )
            return redirect("activate")
        return None


class AdminSuperuserOnlyMiddleware:
    """Restrict the Django admin site to platform superusers only.

    Defense-in-depth alongside the is_staff/is_superuser flags on tenant
    accounts. Runs in ``process_view`` because ``resolver_match`` only exists
    after URL resolution — scoping by the admin namespace keeps app routes
    that merely live under ``/admin/`` (e.g. ``/admin/import-students/``)
    unaffected.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        match = getattr(request, "resolver_match", None)
        if match is None or match.namespace != "admin":
            return None

        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            if match.url_name == "login":
                return None
            from django.shortcuts import redirect

            return redirect("/admin/login/")
        if not user.is_superuser:
            return HttpResponseForbidden(
                "Admin access is restricted to the platform owner."
            )
        return None
