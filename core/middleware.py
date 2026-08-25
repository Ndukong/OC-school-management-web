from django.http import HttpResponseForbidden


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
