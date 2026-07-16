from pathlib import Path
from urllib.parse import urlsplit
import os

import dj_database_url
from django.core.exceptions import ImproperlyConfigured


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


def load_secret_key(debug):
    """Return SECRET_KEY from env/.env, or Django's documented insecure dev
    fallback when DEBUG is True. When DEBUG is False and no SECRET_KEY is
    configured, refuse to start: silently falling back to the hardcoded key
    below in a production deployment would mean every deployment shares (and
    leaks, since it's committed source) the same signing key.
    """
    secret_key = _get_env("SECRET_KEY")
    if secret_key:
        return secret_key
    if debug:
        return "django-insecure-local-dev-key-change-me"
    raise ImproperlyConfigured(
        "SECRET_KEY environment variable is required when DEBUG=false."
    )


def load_anthropic_api_key():
    return _get_env("ANTHROPIC_API_KEY")


def load_database_config():
    """Build the Django DATABASES["default"] entry from DATABASE_URL.

    Falls back to the existing sqlite file when DATABASE_URL is unset or
    empty, so local/CI runs that never set it are unaffected. Parsing is
    delegated to dj-database-url so query-string options (e.g. sslmode)
    land in OPTIONS automatically.
    """
    database_url = _get_env("DATABASE_URL")
    if not database_url:
        return {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }

    config = dj_database_url.parse(database_url)
    if config["ENGINE"] != "django.db.backends.postgresql":
        scheme = urlsplit(database_url).scheme
        raise ValueError(f"Unsupported DATABASE_URL scheme: {scheme!r}")

    return config


def load_debug():
    # Local dev default is True (matches historical behavior); explicit
    # DEBUG=false is required to disable it (e.g. deployment envs).
    return _get_env("DEBUG", "true").lower() in ("1", "true", "yes")


def load_allowed_hosts():
    """Parse comma-separated ALLOWED_HOSTS env into a list. Unset keeps the
    historical empty list — Django's Host-header validation still accepts
    localhost/127.0.0.1/[::1] in that case as long as DEBUG=True (its own
    built-in dev allowlist, not "any Host header"); a DEBUG=False deployment
    must set this explicitly (enforced by guard_debug_allowed_hosts below).
    """
    raw = _get_env("ALLOWED_HOSTS", "")
    return [host.strip() for host in raw.split(",") if host.strip()]


def guard_debug_allowed_hosts(debug, allowed_hosts):
    """Fail-open defense (security review H1, 2026-07-14): forgetting to set
    DEBUG=false in a deployment would otherwise silently bypass
    load_secret_key's hard fail too, and the app would serve the real domain
    configured in ALLOWED_HOSTS with debug pages and the insecure dev
    SECRET_KEY. Local dev never has a reason to set ALLOWED_HOSTS, so treat
    a non-empty value as an unambiguous production signal and refuse to
    start if DEBUG is still true.
    """
    if allowed_hosts and debug:
        raise ImproperlyConfigured(
            "ALLOWED_HOSTS is set but DEBUG=true. If this is a production "
            "deployment, set DEBUG=false."
        )


def load_csrf_trusted_origins():
    """Parse comma-separated CSRF_TRUSTED_ORIGINS env into a list. Unset
    keeps Django's own default (no extra trusted origins)."""
    raw = _get_env("CSRF_TRUSTED_ORIGINS", "")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def load_secure_ssl():
    # Same env-parsing convention as load_debug() above; default "" (off) so
    # local dev/tests are unaffected unless the deployment opts in.
    return _get_env("SECURE_SSL", "").lower() in ("1", "true", "yes")


def load_trusted_proxy_count():
    """Number of trusted reverse-proxy hops in front of this app, or None
    when unset (historical behavior: REMOTE_ADDR is trusted as-is, no
    X-Forwarded-For parsing). A non-integer value fails hard instead of
    silently disabling proxy-aware IP resolution. A negative value also
    fails hard: resolve_client_ip's hops[-trusted_proxy_count] would turn
    into a positive index, trusting the attacker-controlled left end of
    X-Forwarded-For instead of the right end — defeating the spoofing
    defense (0 stays allowed; it is falsy and keeps the safe REMOTE_ADDR
    path)."""
    raw = _get_env("TRUSTED_PROXY_COUNT", "")
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        raise ImproperlyConfigured(
            f"TRUSTED_PROXY_COUNT must be an integer, got {raw!r}."
        )
    if value < 0:
        raise ImproperlyConfigured(
            "TRUSTED_PROXY_COUNT must be an integer 0 or greater, got "
            f"{value!r}."
        )
    return value


def build_axes_client_ip_callable(trusted_proxy_count):
    """AXES_CLIENT_IP_CALLABLE dotted path, or None to keep axes' own
    REMOTE_ADDR-based default. Only opt into core.ip.get_client_ip when a
    trusted proxy hop count is configured; otherwise the historical
    REMOTE_ADDR behavior is unchanged."""
    return "core.ip.get_client_ip" if trusted_proxy_count else None


def load_staticfiles_storage(debug):
    """Static files storage backend for STORAGES["staticfiles"].

    CompressedManifestStaticFilesStorage requires a manifest
    (staticfiles.json) written by `collectstatic`, which local dev and the
    test suite never run — resolving {% static %} against it there raises
    ValueError. DEBUG=true (dev and every test run: DEBUG defaults to true,
    see load_debug()) keeps the plain filesystem storage so behavior is
    unchanged from before whitenoise; only a DEBUG=false deployment (which
    runs collectstatic before serving, see PR-0b — verified locally: 210
    copied, 610 post-processed, manifest generated) gets the compressed/
    manifest/whitenoise backend.
    """
    if debug:
        return "django.contrib.staticfiles.storage.StaticFilesStorage"
    return "whitenoise.storage.CompressedManifestStaticFilesStorage"


def load_media_storage_config():
    """Media storage backend for STORAGES["default"].

    Unset MEDIA_STORAGE_BUCKET keeps the existing local-disk FileSystemStorage
    (dev/CI/PaaS-less deployments unaffected).
    """
    bucket = _get_env("MEDIA_STORAGE_BUCKET")
    if not bucket:
        return {"BACKEND": "django.core.files.storage.FileSystemStorage"}

    access_key = _get_env("MEDIA_STORAGE_ACCESS_KEY_ID")
    secret_key = _get_env("MEDIA_STORAGE_SECRET_ACCESS_KEY")
    endpoint_url = _get_env("MEDIA_STORAGE_ENDPOINT_URL")
    # REGION is excluded from this check: it has a real default ("auto",
    # below), so an unset value is a valid configuration, not a mistake.
    required = {
        "MEDIA_STORAGE_ACCESS_KEY_ID": access_key,
        "MEDIA_STORAGE_SECRET_ACCESS_KEY": secret_key,
        "MEDIA_STORAGE_ENDPOINT_URL": endpoint_url,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise ImproperlyConfigured(
            "MEDIA_STORAGE_BUCKET is set but "
            f"{', '.join(missing)} is missing. A partially configured "
            "object storage backend would silently upload with empty "
            "credentials and only fail on first use — set all of "
            "MEDIA_STORAGE_ACCESS_KEY_ID, MEDIA_STORAGE_SECRET_ACCESS_KEY, "
            "and MEDIA_STORAGE_ENDPOINT_URL, or unset MEDIA_STORAGE_BUCKET "
            "to keep local-disk storage."
        )
    return {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "bucket_name": bucket,
            "access_key": access_key,
            "secret_key": secret_key,
            "endpoint_url": endpoint_url,
            # "auto" is Cloudflare R2's documented region value for its S3
            # API (R2/B2 don't use AWS regions); harmless default when the
            # deployment doesn't set MEDIA_STORAGE_REGION explicitly.
            "region_name": _get_env("MEDIA_STORAGE_REGION", "auto"),
        },
    }


def build_secure_ssl_settings(secure_ssl):
    """Extra settings applied when running behind a TLS-terminating reverse
    proxy (PaaS router). Empty dict when secure_ssl is False, so nothing here
    is set and Django's own (all off/zero) defaults apply — local dev/tests
    are unaffected. Only enable when the proxy is guaranteed to set (and
    strip any client-supplied) X-Forwarded-Proto — see .env.example.
    """
    if not secure_ssl:
        return {}
    return {
        "SECURE_PROXY_SSL_HEADER": ("HTTP_X_FORWARDED_PROTO", "https"),
        "SECURE_SSL_REDIRECT": True,
        "SECURE_HSTS_SECONDS": 31536000,
        "SECURE_HSTS_INCLUDE_SUBDOMAINS": True,
        # Preload requires submitting the domain to browser HSTS preload
        # lists, which is hard to reverse — stay conservative until that's a
        # deliberate, separate decision.
        "SECURE_HSTS_PRELOAD": False,
    }


ANTHROPIC_API_KEY = load_anthropic_api_key()
LLM_MODEL = "claude-haiku-4-5-20251001"
LLM_TIMEOUT_SECONDS = 10
LLM_MAX_TOKENS = 1024
# Escalation tier when heuristic/LLM field confidence is low (drafts/llm_extraction.py).
LLM_ESCALATION_MODEL = "claude-sonnet-5"
LLM_ESCALATION_CONFIDENCE_THRESHOLD = 0.6
# Wiring flag (PR-C connects create_draft_from_url to extract_event_fields_llm).
DRAFT_LLM_EXTRACTION_ENABLED = False
# Contact URL appended to the crawl User-Agent (drafts/fetching.py) so a site
# operator can reach us about the bot; blank keeps the current bare UA.
DRAFT_FETCH_CONTACT = ""
# Gate for the discover_drafts management command (prompt_plan.md §2-5) — off
# by default so no crawling happens until an operator opts in.
DRAFT_DISCOVERY_ENABLED = False
# Caps a single discover_drafts run: total new drafts created across every
# source, independent of the per-source fetch cap below.
DRAFT_DISCOVERY_MAX_PER_RUN = 10
# Caps per-source fetch *attempts* (robots checks + create_draft_from_url
# calls) so a source yielding mostly empty/duplicate candidates cannot be
# re-hit indefinitely while chasing the creation cap above.
DRAFT_DISCOVERY_MAX_FETCHES_PER_SOURCE = 20
# Staff dashboard freshness threshold: an enabled DraftSource whose
# last_checked_at is older than this (or still None) is flagged "stale" —
# 48h covers a couple of missed daily runs before it reads as a problem.
DRAFT_SOURCE_STALE_HOURS = 48
DEBUG = load_debug()
SECRET_KEY = load_secret_key(DEBUG)
ALLOWED_HOSTS = load_allowed_hosts()
guard_debug_allowed_hosts(DEBUG, ALLOWED_HOSTS)
CSRF_TRUSTED_ORIGINS = load_csrf_trusted_origins()

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
    "allauth.socialaccount.providers.google",
    "accounts",
    "events",
    "drafts",
    "archive",
    "core",
    "staff",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # Serves collected static files directly from the app process — no
    # separate static-file server/CDN needed for the initial deployment.
    # Must sit right after SecurityMiddleware (whitenoise docs).
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
                "core.context_processors.google_oauth_configured",
                "core.context_processors.support_email",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {"default": load_database_config()}

# Shared cache (G11): gunicorn runs multiple worker processes, and the default
# LocMemCache is per-process — rate limits (allauth ACCOUNT_RATE_LIMITS,
# accounts.views delete-attempt lockout) would silently reset per worker and
# on every redeploy. DatabaseCache reuses the already-provisioned Postgres
# (no new service) and is shared across all workers/redeploys. Applied
# unconditionally (no env gate) so dev/test and production share the same
# backend and the "django_cache" table (created by the core migration below)
# is always exercised.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
    }
}

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
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": load_media_storage_config(),
    "staticfiles": {"BACKEND": load_staticfiles_storage(DEBUG)},
}
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
LOGIN_REDIRECT_URL = "/collection/"
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
# Custom signup form adds the mandatory terms/privacy-policy agreement
# checkbox (accounts/forms.py) on top of allauth's default email/password
# fields.
ACCOUNT_FORMS = {"signup": "accounts.forms.SignupForm"}

# django-allauth socialaccount: Google sign-in. Credentials come from env
# (never committed); register the OAuth client in Google Cloud Console with the
# redirect URI /accounts/google/login/callback/ (localhost for dev, the real
# host for prod). Blank env hides the button (see
# core.context_processors.google_oauth_configured) until credentials are set.
SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APPS": [
            {
                "client_id": _get_env("GOOGLE_CLIENT_ID"),
                "secret": _get_env("GOOGLE_CLIENT_SECRET"),
                "key": "",
            }
        ],
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    }
}
# Google verifies email ownership, so trust it: a Google login whose verified
# email matches an existing local account logs into that account and connects
# the Google account to it. SAFE ONLY because Google is a fully-trusted
# provider — revisit this if another (less-trusted) provider is ever added.
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

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
# NOTE (deployment): behind a reverse proxy, set the TRUSTED_PROXY_COUNT env
# var to the real number of proxy hops so axes locks out the real attacker
# IP instead of the proxy IP (which would lock out everyone). This wires
# AXES_CLIENT_IP_CALLABLE to core.ip.get_client_ip; unset TRUSTED_PROXY_COUNT
# keeps axes' own REMOTE_ADDR-based default (see core/ip.py for why
# django-axes' AXES_IPWARE_* settings are not used here — this project does
# not depend on django-ipware).
TRUSTED_PROXY_COUNT = load_trusted_proxy_count()
AXES_CLIENT_IP_CALLABLE = build_axes_client_ip_callable(TRUSTED_PROXY_COUNT)

# Secure cookies: disabled in development (http), enabled when SECURE_COOKIES env is set.
_secure_cookies = os.environ.get("SECURE_COOKIES", "").lower() in ("1", "true", "yes")
SESSION_COOKIE_SECURE = _secure_cookies
CSRF_COOKIE_SECURE = _secure_cookies
# Keep CSRF_COOKIE_HTTPONLY False so the JS layer can read the csrftoken cookie.
CSRF_COOKIE_HTTPONLY = False

# Proxy/HTTPS security headers: opt-in via SECURE_SSL env (deployment behind a
# TLS-terminating reverse proxy). Independent of SECURE_COOKIES above — kept
# as a separate flag rather than reusing it (G4).
SECURE_SSL = load_secure_ssl()
_secure_ssl_settings = build_secure_ssl_settings(SECURE_SSL)
if _secure_ssl_settings:
    SECURE_PROXY_SSL_HEADER = _secure_ssl_settings["SECURE_PROXY_SSL_HEADER"]
    SECURE_SSL_REDIRECT = _secure_ssl_settings["SECURE_SSL_REDIRECT"]
    SECURE_HSTS_SECONDS = _secure_ssl_settings["SECURE_HSTS_SECONDS"]
    SECURE_HSTS_INCLUDE_SUBDOMAINS = _secure_ssl_settings["SECURE_HSTS_INCLUDE_SUBDOMAINS"]
    SECURE_HSTS_PRELOAD = _secure_ssl_settings["SECURE_HSTS_PRELOAD"]

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
# Contact address shown on the legal pages / footer for user inquiries and
# data-rights requests. Placeholder domain until the real support inbox is
# provisioned (see .docs/plans/2026-07-10-legal-pages-plan.md §3-2) — swap
# via env only, no code change needed once the real address exists.
SUPPORT_EMAIL = _get_env("SUPPORT_EMAIL", "support@takulife.example")

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

# Console logging (stdout), matching a PaaS deployment where the platform
# collects stdout — no file handlers, no external log service (G8). django
# and root default to INFO; django.request is raised to ERROR so unhandled
# 5xx exceptions print with a stack trace, without also emitting Django's own
# per-request INFO/WARNING noise (404s, etc.) at every request.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "{asctime} {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console"],
            "level": "ERROR",
            "propagate": False,
        },
    },
}
