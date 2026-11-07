from django.conf import settings


def auth_providers(request):
    return {"google_oauth_enabled": settings.GOOGLE_OAUTH_ENABLED}
