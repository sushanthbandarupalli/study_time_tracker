from allauth.account.forms import SignupForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError


class StudyTrackSignupForm(SignupForm):
    def clean_username(self):
        try:
            username = super().clean_username().strip().lower()
        except ValidationError:
            normalized_username = self.cleaned_data["username"].strip().lower()
            if get_user_model().objects.filter(
                username__iexact=normalized_username
            ).exists():
                raise ValidationError("This username is already taken.")
            raise
        if get_user_model().objects.filter(username__iexact=username).exists():
            raise ValidationError("This username is already taken.")
        return username
