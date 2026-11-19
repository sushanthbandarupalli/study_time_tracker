import time

from django.core.exceptions import ValidationError
from django.urls import reverse

from allauth.socialaccount.adapter import DefaultSocialAccountAdapter

from .auth_utils import (
    GOOGLE_AUTH_TIMESTAMP_SESSION_KEY,
    GOOGLE_AUTH_UID_SESSION_KEY,
)


class StudyTrackSocialAccountAdapter(DefaultSocialAccountAdapter):
    def pre_social_login(self, request, sociallogin):
        super().pre_social_login(request, sociallogin)
        if sociallogin.account.provider == "google":
            request.session[GOOGLE_AUTH_TIMESTAMP_SESSION_KEY] = time.time()
            request.session[GOOGLE_AUTH_UID_SESSION_KEY] = sociallogin.account.uid

    def get_connect_redirect_url(self, request, socialaccount):
        return reverse("account_recovery_setup")

    def validate_disconnect(self, account, accounts):
        if account.provider == "google":
            raise ValidationError(
                "A Google account must stay linked so you can recover your password."
            )
        super().validate_disconnect(account, accounts)
