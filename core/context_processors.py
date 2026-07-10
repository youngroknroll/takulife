from django.conf import settings


def project_name(request):
    """Inject the product name into every template context.

    Keeps views from each hardcoding ``"project_name"`` in their render context.
    """
    return {"project_name": "takulife"}


def google_oauth_configured(request):
    """Whether the Google OAuth client_id is set, so templates can hide the
    Google sign-in button instead of showing a non-functional one.
    """
    apps = settings.SOCIALACCOUNT_PROVIDERS.get("google", {}).get("APPS", [])
    client_id = apps[0].get("client_id", "") if apps else ""
    return {"google_oauth_configured": bool(client_id)}


def support_email(request):
    """Inject the contact address (legal pages, footer) into every template
    context, so views don't each hardcode ``"support_email"``.
    """
    return {"support_email": settings.SUPPORT_EMAIL}
