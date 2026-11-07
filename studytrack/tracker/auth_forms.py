from allauth.account.forms import SignupForm
from allauth.account.models import EmailAddress
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError


class StudyTrackSignupForm(SignupForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.account_already_registered = False

    def clean_email(self):
        email = super().clean_email()
        if email and (
            EmailAddress.objects.filter(email__iexact=email).exists()
            or get_user_model().objects.filter(email__iexact=email).exists()
        ):
            self.account_already_registered = True
            raise ValidationError("This email is already registered. Please try signing in.")
        return email
