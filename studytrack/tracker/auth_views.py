from django.contrib import messages
from django.contrib.auth import get_user_model, logout, update_session_auth_hash
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError, transaction
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import FormView, TemplateView

from allauth.account.views import SignupView as AllauthSignupView

from .auth_utils import (
    GOOGLE_AUTH_TIMESTAMP_SESSION_KEY,
    GOOGLE_AUTH_UID_SESSION_KEY,
    has_google_account,
    has_recent_google_authentication,
)


class SignupView(AllauthSignupView):
    def form_valid(self, form):
        try:
            with transaction.atomic():
                response = super().form_valid(form)
                logout(self.request)
                return response
        except IntegrityError:
            username = form.cleaned_data["username"]
            if not get_user_model().objects.filter(username__iexact=username).exists():
                raise
            form.add_error("username", "This username is already taken.")
            return self.form_invalid(form)

    def get_success_url(self):
        return reverse("account_signup_success")


class SignupSuccessView(TemplateView):
    template_name = "account/signup_success.html"


class PasswordRecoveryView(TemplateView):
    template_name = "account/password_recovery.html"


class GoogleRecoverySetupView(LoginRequiredMixin, TemplateView):
    template_name = "account/recovery_setup.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["google_linked"] = has_google_account(self.request.user)
        return context


class SetPasswordView(LoginRequiredMixin, FormView):
    template_name = "account/password_set.html"
    form_class = SetPasswordForm

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            if not has_google_account(request.user):
                return redirect("account_recovery_setup")
            self.requires_google_reauthentication = not has_recent_google_authentication(
                request, request.user
            )
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def get(self, request, *args, **kwargs):
        if getattr(self, "requires_google_reauthentication", False):
            return self.render_to_response(self.get_context_data())
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        if getattr(self, "requires_google_reauthentication", False):
            return self.get(request, *args, **kwargs)
        return super().post(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["requires_google_reauthentication"] = getattr(
            self, "requires_google_reauthentication", False
        )
        return context

    def form_valid(self, form):
        user = form.save()
        update_session_auth_hash(self.request, user)
        self.request.session.pop(GOOGLE_AUTH_TIMESTAMP_SESSION_KEY, None)
        self.request.session.pop(GOOGLE_AUTH_UID_SESSION_KEY, None)
        messages.success(self.request, "Your password has been updated.")
        return redirect("account_recovery_setup")
