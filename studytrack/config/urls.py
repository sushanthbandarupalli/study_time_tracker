from django.contrib import admin
from django.urls import include, path
from tracker.auth_views import (
    GoogleRecoverySetupView,
    PasswordRecoveryView,
    SetPasswordView,
    SignupSuccessView,
    SignupView,
)
from tracker.views import health

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/signup/", SignupView.as_view(), name="account_signup"),
    path("accounts/signup/success/", SignupSuccessView.as_view(), name="account_signup_success"),
    path("accounts/recovery/", GoogleRecoverySetupView.as_view(), name="account_recovery_setup"),
    path("accounts/password/recovery/", PasswordRecoveryView.as_view(), name="account_password_recovery"),
    path("accounts/password/set/", SetPasswordView.as_view(), name="account_set_password"),
    path("accounts/", include("allauth.urls")),
    path("health/", health, name="health"),
    path("", include("tracker.urls")),
]
