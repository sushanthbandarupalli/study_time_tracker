from django.contrib import admin
from django.urls import include, path
from tracker.auth_views import ConfirmEmailVerificationCodeView, SignupView
from tracker.views import health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/signup/", SignupView.as_view(), name="account_signup"),
    path(
        "accounts/confirm-email/",
        ConfirmEmailVerificationCodeView.as_view(),
        name="account_email_verification_sent",
    ),
    path("accounts/", include("allauth.urls")),
    path("health/", health, name="health"),
    path("", include("tracker.urls")),
]
