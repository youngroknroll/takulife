from pathlib import Path
from urllib.parse import unquote, urlsplit
import os


BASE_DIR = Path(__file__).resolve().parent.parent


def _get_env(name, default=""):
    env_value = os.environ.get(name)
    if env_value is not None:
        return env_value

    env_path = BASE_DIR / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator and key.strip() == name:
                return value.strip().strip("'\"")

    return default


def load_secret_key():
    return _get_env("SECRET_KEY") or "django-insecure-local-dev-key-change-me"


def load_anthropic_api_key():
    return _get_env("ANTHROPIC_API_KEY")


_POSTGRES_SCHEMES = ("postgres", "postgresql")


def load_database_config():
    """Build the Django DATABASES["default"] entry from DATABASE_URL.

    Falls back to the existing sqlite file when DATABASE_URL is unset or
    empty, so local/CI runs that never set it are unaffected.
    """
    database_url = _get_env("DATABASE_URL")
    if not database_url:
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }

    parsed = urlsplit(database_url)
    if parsed.scheme not in _POSTGRES_SCHEMES:
        raise ValueError(f"Unsupported DATABASE_URL scheme: {parsed.scheme!r}")

    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parsed.path.lstrip("/")),
        "USER": unquote(parsed.username) if parsed.username else "",
        "PASSWORD": unquote(parsed.password) if parsed.password else "",
        "HOST": parsed.hostname or "localhost",
        "PORT": str(parsed.port) if parsed.port else "5432",
    }


SECRET_KEY = load_secret_key()
ANTHROPIC_API_KEY = load_anthropic_api_key()
LLM_MODEL = "claude-haiku-4-5-20251001"
LLM_TIMEOUT_SECONDS = 10
LLM_MAX_TOKENS = 1024
# Escalation tier when heuristic/LLM field confidence is low (drafts/llm_extraction.py).
LLM_ESCALATION_MODEL = "claude-sonnet-5"
LLM_ESCALATION_CONFIDENCE_THRESHOLD = 0.6
# Wiring flag (PR-C connects create_draft_from_url to extract_event_fields_llm).
DRAFT_LLM_EXTRACTION_ENABLED = False
DEBUG = True
ALLOWED_HOSTS = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.sites",
    "django.contrib.staticfiles",
    "rest_framework",
    "axes",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "accounts",
    "events",
    "drafts",
    "archive",
    "core",
    "staff",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # AxesMiddleware must come last so it can render the lockout response after
    # authentication has run.
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.project_name",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {"default": load_database_config()}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "accounts.User"
SITE_ID = 1

AUTHENTICATION_BACKENDS = [
    # AxesStandaloneBackend must be first: it short-circuits authentication with
    # PermissionDenied once an IP is locked out, without itself validating creds.
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/archive/"
LOGOUT_REDIRECT_URL = "/"

# django-allauth: email-only identifier, mandatory verification before login.
# ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION replaces the old auto-login-on-register
# policy — the session is only granted once the confirmation link is clicked.
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 3

# Rate limits on the auth endpoints (brute-force / signup-flood defense).
# allauth ships sane defaults that are already active; this dict is MERGED over
# those defaults (allauth: `ret.update(rls)`), so unlisted actions keep their
# allauth default. We pin the security-relevant actions here for auditability
# and tighten `signup` for public deployment. Format: "<count>/<duration>/<scope>",
# scope is ip|key|user, comma-combines multiple windows (all must pass).
#   - signup: burst 5/min + sustained 30/hour per IP (default is a looser 20/m/ip)
#   - login_failed: 10/min per IP + 5 per 5min per account; once the per-account
#     window is spent the login form refuses further auth (even the correct
#     password) until it cools off. Durable IP lockout is a follow-up (B1b: axes).
#   - reset_password: throttles password-reset email requests (allauth default).
# Rate-limit hits render templates/429.html.
ACCOUNT_RATE_LIMITS = {
    "signup": "5/m/ip,30/h/ip",
    "login_failed": "10/m/ip,5/300s/key",
    "reset_password": "20/m/ip,5/m/key",
}

# django-axes: durable brute-force lockout on top of allauth's per-window
# throttle. allauth refuses further auth within a rolling window; axes adds a
# hard lockout with a cool-off so repeated attackers are shut out and visible
# in the admin (AccessAttempt/AccessLog). Lock by IP only — locking by username
# would let an attacker lock a victim out (DoS); the per-account dimension is
# already covered by allauth's login_failed `key` limit.
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # hours
AXES_LOCKOUT_PARAMETERS = ["ip_address"]
AXES_RESET_ON_SUCCESS = True
AXES_HTTP_RESPONSE_CODE = 429
AXES_LOCKOUT_TEMPLATE = "account/lockout.html"
# allauth posts the identifier under the form field named "login"; axes must
# read the same field to record attempts against the right credential.
AXES_USERNAME_FORM_FIELD = "login"
# NOTE (deployment): behind a reverse proxy, configure AXES_IPWARE_* so the real
# client IP is used — otherwise every request looks like the proxy IP and one
# attacker can lock out everyone. Do not enable in prod until the proxy is set.

# Secure cookies: disabled in development (http), enabled when SECURE_COOKIES env is set.
_secure_cookies = os.environ.get("SECURE_COOKIES", "").lower() in ("1", "true", "yes")
SESSION_COOKIE_SECURE = _secure_cookies
CSRF_COOKIE_SECURE = _secure_cookies
# Keep CSRF_COOKIE_HTTPONLY False so the JS layer can read the csrftoken cookie.
CSRF_COOKIE_HTTPONLY = False

# Email (django-allauth verification / password reset). Blank EMAIL_HOST falls
# back to the console backend so local dev never needs real SMTP credentials.
EMAIL_HOST = _get_env("EMAIL_HOST")
EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend"
    if EMAIL_HOST
    else "django.core.mail.backends.console.EmailBackend"
)
EMAIL_PORT = int(_get_env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = _get_env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = _get_env("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = _get_env("EMAIL_USE_TLS", "true").lower() in ("1", "true", "yes")
DEFAULT_FROM_EMAIL = _get_env("DEFAULT_FROM_EMAIL", "no-reply@takulife.example")

# DRF: rate-limit 공식 제보 (promotion) so an authenticated user cannot flood the
# admin review queue with promoted PersonalEntry drafts. Scoped throttle only —
# applied per-view (PromotePersonalEntryView), so other endpoints are unaffected.
REST_FRAMEWORK = {
    # Session auth only — the app is browser/session based. Dropping the DRF
    # default BasicAuthentication closes a CSRF-bypass hole: Basic-authenticated
    # requests skip CSRF, which would let a staff credential mutate via forged
    # cross-site requests. SessionAuthentication enforces CSRF on unsafe methods.
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "promotion": "20/day",
    },
}
