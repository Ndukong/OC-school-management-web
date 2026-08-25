from django.http import HttpResponseForbidden


class AdminSuperuserOnlyMiddleware:
    """Restrict Django admin (/admin/*) to platform superusers only.

    Defense-in-depth alongside is_staff/is_superuser flags on tenant accounts:
    - Anonymous visitors are redirected to the admin login page.
    - Authenticated non-superusers (any tenant account) receive 403.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if path.startswith("/admin"):
            user = getattr(request, "user", None)
            if user is None or not user.is_authenticated:
                if not path.startswith("/admin/login"):
                    from django.shortcuts import redirect

                    return redirect("/admin/login/")
            elif not user.is_superuser:
                return HttpResponseForbidden(
                    "Admin access is restricted to the platform owner."
                )
        return self.get_response(request)
