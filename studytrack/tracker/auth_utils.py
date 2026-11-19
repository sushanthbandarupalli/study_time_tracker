import time

from allauth.socialaccount.models import SocialAccount

GOOGLE_AUTH_TIMESTAMP_SESSION_KEY = "studytrack_google_auth_timestamp"
GOOGLE_AUTH_UID_SESSION_KEY = "studytrack_google_auth_uid"
GOOGLE_AUTH_MAX_AGE_SECONDS = 5 * 60


def has_google_account(user):
    return user.is_authenticated and SocialAccount.objects.filter(
        user=user, provider="google"
    ).exists()


def has_recent_google_authentication(request, user):
    timestamp = request.session.get(GOOGLE_AUTH_TIMESTAMP_SESSION_KEY)
    google_uid = request.session.get(GOOGLE_AUTH_UID_SESSION_KEY)
    if not isinstance(timestamp, (int, float)) or not isinstance(google_uid, str):
        return False

    age = time.time() - timestamp
    return (
        0 <= age <= GOOGLE_AUTH_MAX_AGE_SECONDS
        and SocialAccount.objects.filter(
            user=user, provider="google", uid=google_uid
        ).exists()
    )
