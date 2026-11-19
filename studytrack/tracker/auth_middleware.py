from django.conf import settings
from django.shortcuts import redirect

from .auth_utils import has_google_account


class GoogleRecoveryRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        request.google_recovery_required = False
        if path.startswith("/accounts/password/reset/"):
            return redirect("account_password_recovery")

        static_prefix = "/" + settings.STATIC_URL.lstrip("/")
        if request.user.is_authenticated and not request.user.is_superuser:
            request.google_recovery_required = not has_google_account(request.user)
            if (
                request.google_recovery_required
                and path != "/health/"
                and not path.startswith(("/accounts/", "/admin/", static_prefix))
            ):
                return redirect("account_recovery_setup")

        return self.get_response(request)
