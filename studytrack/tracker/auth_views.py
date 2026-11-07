import logging
import smtplib

from django.contrib import messages
from django.db import transaction
from django.http import HttpResponseRedirect

from allauth.account.views import (
    ConfirmEmailVerificationCodeView as AllauthConfirmEmailVerificationCodeView,
    SignupView as AllauthSignupView,
)
from django.urls import reverse

logger = logging.getLogger(__name__)
OTP_DELIVERY_ERROR = "Unable to send the OTP. Please check the email address and try again."


class SignupView(AllauthSignupView):
    def form_valid(self, form):
        try:
            with transaction.atomic():
                return super().form_valid(form)
        except (OSError, smtplib.SMTPException):
            logger.exception("Could not send the signup verification code.")
            form.add_error(None, OTP_DELIVERY_ERROR)
            response = self.form_invalid(form)
            response.status_code = 503
            return response


class ConfirmEmailVerificationCodeView(AllauthConfirmEmailVerificationCodeView):
    def _resend_form_valid(self, form):
        try:
            return super()._resend_form_valid(form)
        except (OSError, smtplib.SMTPException):
            logger.exception("Could not resend the email verification code.")
            messages.error(self.request, OTP_DELIVERY_ERROR)
            return HttpResponseRedirect(
                self.passthrough_next_url(reverse("account_email_verification_sent"))
            )

    def _change_form_valid(self, form):
        try:
            with transaction.atomic():
                return super()._change_form_valid(form)
        except (OSError, smtplib.SMTPException):
            logger.exception("Could not send a verification code to the updated email.")
            messages.error(self.request, OTP_DELIVERY_ERROR)
            return HttpResponseRedirect(
                self.passthrough_next_url(reverse("account_email_verification_sent"))
            )
