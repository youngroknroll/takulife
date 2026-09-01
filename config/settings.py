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
    """SECRET_KEY를 env/.env에서 읽거나, DEBUG일 때만 Django 기본 개발용
    키로 대체한다. DEBUG=false인데 SECRET_KEY가 없으면 실행을 막는다 —
    조용히 아래 하드코딩 키로 넘어가면 배포마다 같은 서명 키를 공유하고,
    그 키는 소스에 커밋돼 있어 이미 노출된 것이나 다름없다.
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


def load_draft_fetch_contact():
    # 크롤링 UA에 붙는 연락처를 운영자가 env로 지정한다.
    return _get_env("DRAFT_FETCH_CONTACT", "")


def load_database_config():
    """DATABASE_URL로 Django DATABASES["default"] 값을 만든다.

    DATABASE_URL이 비어 있으면 기존 sqlite 파일로 대체해 로컬/CI가 영향받지
    않는다. 파싱은 dj-database-url에 맡겨 sslmode 같은 쿼리스트링 옵션이
    자동으로 OPTIONS에 들어가게 한다.
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
    # 로컬 개발 기본값은 True. 배포 환경처럼 끄려면 DEBUG=false를 명시해야 한다.
    return _get_env("DEBUG", "true").lower() in ("1", "true", "yes")


def load_draft_discovery_enabled():
    # 기본값은 꺼짐 — 실수로 자동 크롤링이 켜져 외부 사이트를 무단으로
    # 긁지 않도록 명시적 옵트인(DRAFT_DISCOVERY_ENABLED=true)을 요구한다.
    return _get_env("DRAFT_DISCOVERY_ENABLED", "false").lower() in ("1", "true", "yes")


def load_allowed_hosts():
    """콤마로 구분된 ALLOWED_HOSTS env를 리스트로 만든다. 비어 있으면 기존과
    같이 빈 리스트를 쓰는데, DEBUG=True인 동안은 Django가 자체적으로
    localhost/127.0.0.1/[::1]만 허용하므로 문제없다("모든 Host 허용"이
    아니다). DEBUG=False 배포는 이 값을 반드시 직접 설정해야 하고, 그건
    아래 guard_debug_allowed_hosts가 강제한다.
    """
    raw = _get_env("ALLOWED_HOSTS", "")
    return [host.strip() for host in raw.split(",") if host.strip()]


def guard_debug_allowed_hosts(debug, allowed_hosts):
    """배포에서 DEBUG=false 설정을 깜빡하면 load_secret_key의 강제 실패도
    조용히 우회되고, 실제 도메인이 디버그 페이지와 안전하지 않은 개발용
    SECRET_KEY로 서비스될 수 있다. 로컬 개발은 ALLOWED_HOSTS를 설정할
    이유가 없으므로, 값이 채워져 있는데 DEBUG가 여전히 true면 확실한 설정
    실수로 보고 실행을 막는다.
    """
    if allowed_hosts and debug:
        raise ImproperlyConfigured(
            "ALLOWED_HOSTS is set but DEBUG=true. If this is a production "
            "deployment, set DEBUG=false."
        )


def load_csrf_trusted_origins():
    """콤마로 구분된 CSRF_TRUSTED_ORIGINS env를 리스트로 만든다. 비어 있으면
    Django 기본값(추가 신뢰 출처 없음)을 그대로 쓴다."""
    raw = _get_env("CSRF_TRUSTED_ORIGINS", "")
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def load_secure_ssl():
    # 위 load_debug()와 같은 env 파싱 방식. 기본값은 꺼짐이라 배포가 직접
    # 켜지 않는 한 로컬 개발·테스트는 영향받지 않는다.
    return _get_env("SECURE_SSL", "").lower() in ("1", "true", "yes")


def load_trusted_proxy_count():
    """이 앱 앞단의 신뢰할 수 있는 리버스 프록시 홉 수. 비어 있으면 None을
    반환해 기존처럼 REMOTE_ADDR을 그대로 신뢰한다(X-Forwarded-For 파싱
    없음). 정수가 아니면 조용히 무시하지 않고 실행을 막는다. 음수도 막는데,
    resolve_client_ip의 hops[-trusted_proxy_count] 인덱스가 양수로 뒤집혀
    공격자가 조작 가능한 X-Forwarded-For의 왼쪽 끝을 신뢰하게 되어 스푸핑
    방어가 무력화되기 때문이다(0은 falsy라 안전한 REMOTE_ADDR 경로를
    유지하므로 허용된다)."""
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


def load_email_port():
    """EMAIL_PORT env를 정수로 캐스팅한다. 정수가 아니면 조용히 무시하지
    않고 실행을 막는다(load_trusted_proxy_count와 같은 방어 관용구)."""
    raw = _get_env("EMAIL_PORT", "587")
    try:
        return int(raw)
    except ValueError:
        raise ImproperlyConfigured(f"EMAIL_PORT must be an integer, got {raw!r}.")


def build_axes_client_ip_callable(trusted_proxy_count):
    """AXES_CLIENT_IP_CALLABLE 경로를 반환하거나, axes 기본
    REMOTE_ADDR 방식을 유지하려면 None을 반환한다. 신뢰 프록시 홉 수가
    설정된 경우에만 core.ip.get_client_ip를 쓰고, 그 외엔 기존 동작 그대로."""
    return "core.ip.get_client_ip" if trusted_proxy_count else None


def load_staticfiles_storage(debug):
    """STORAGES["staticfiles"]에 쓸 정적 파일 저장 백엔드.

    CompressedManifestStaticFilesStorage는 `collectstatic`이 생성하는
    매니페스트(staticfiles.json)가 필요한데, 로컬 개발과 테스트는
    collectstatic을 돌리지 않아 {% static %} 해석 시 ValueError가 난다.
    DEBUG=true(개발·모든 테스트 실행의 기본값)에서는 기존 방식인 일반
    파일시스템 저장소를 유지하고, collectstatic을 먼저 실행하는
    DEBUG=false 배포에서만 압축/매니페스트 whitenoise 백엔드를 쓴다.
    """
    if debug:
        return "django.contrib.staticfiles.storage.StaticFilesStorage"
    return "whitenoise.storage.CompressedManifestStaticFilesStorage"


def load_media_storage_config():
    """STORAGES["default"]에 쓸 미디어 저장 백엔드.

    MEDIA_STORAGE_BUCKET이 비어 있으면 기존 로컬 디스크
    FileSystemStorage를 유지해 개발/CI/PaaS 미사용 배포는 영향받지 않는다.
    """
    bucket = _get_env("MEDIA_STORAGE_BUCKET")
    if not bucket:
        return {"BACKEND": "django.core.files.storage.FileSystemStorage"}

    access_key = _get_env("MEDIA_STORAGE_ACCESS_KEY_ID")
    secret_key = _get_env("MEDIA_STORAGE_SECRET_ACCESS_KEY")
    endpoint_url = _get_env("MEDIA_STORAGE_ENDPOINT_URL")
    # REGION은 이 검사에서 제외한다 — 아래에 실제 기본값("auto")이 있어
    # 비어 있어도 정상 설정이지 실수가 아니다.
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
            # "auto"는 Cloudflare R2 S3 API의 공식 리전 값이다(R2/B2는
            # AWS 리전 개념이 없음). MEDIA_STORAGE_REGION 미설정 시 무해한 기본값.
            "region_name": _get_env("MEDIA_STORAGE_REGION", "auto"),
            # 같은 파일명 업로드가 타인 사진을 소리 없이 덮어쓰는 것을
            # 막는 방어선(파일명 자체는 업로드 경로에서 UUID로 생성).
            "file_overwrite": False,
            # R2는 x-amz-acl 헤더를 지원하지 않아 어떤 문자열 값이든
            # 업로드가 실패한다. None은 헤더를 아예 보내지 않는다는 뜻이고,
            # 실제 비공개는 버킷 설정이 보증한다(런북 체크리스트).
            "default_acl": None,
            # 서명 URL(만료 있음)로만 접근되게 하는 계약을 명시 고정한다.
            "querystring_auth": True,
        },
    }


def build_secure_ssl_settings(secure_ssl):
    """TLS를 종료하는 리버스 프록시(PaaS 라우터) 뒤에서 실행할 때 추가로
    적용할 설정. secure_ssl이 False면 빈 dict를 반환해 Django 기본값(전부
    꺼짐)을 유지하므로 로컬 개발·테스트는 영향받지 않는다. 프록시가
    X-Forwarded-Proto를 확실히 설정(및 클라이언트가 보낸 값은 제거)하는
    경우에만 켜야 한다 — .env.example 참고.
    """
    if not secure_ssl:
        return {}
    return {
        "SECURE_PROXY_SSL_HEADER": ("HTTP_X_FORWARDED_PROTO", "https"),
        "SECURE_SSL_REDIRECT": True,
        "SECURE_HSTS_SECONDS": 31536000,
        "SECURE_HSTS_INCLUDE_SUBDOMAINS": True,
        # Preload는 브라우저 HSTS 프리로드 목록에 도메인을 등록해야 하고
        # 되돌리기 어렵다 — 별도로 신중히 결정하기 전까지는 꺼둔다.
        "SECURE_HSTS_PRELOAD": False,
    }


ANTHROPIC_API_KEY = load_anthropic_api_key()
LLM_MODEL = "claude-haiku-4-5-20251001"
LLM_TIMEOUT_SECONDS = 10
LLM_MAX_TOKENS = 1024
# 휴리스틱/LLM 필드 신뢰도가 낮을 때 올라가는 상위 모델(drafts/llm_extraction.py).
LLM_ESCALATION_MODEL = "claude-sonnet-5"
LLM_ESCALATION_CONFIDENCE_THRESHOLD = 0.6
# create_draft_from_url과 extract_event_fields_llm을 연결하는 스위치.
DRAFT_LLM_EXTRACTION_ENABLED = False
# 크롤링 User-Agent(drafts/fetching.py)에 붙는 연락처 URL — 사이트 운영자가
# 봇에 대해 문의할 수 있게 한다. 비워두면 기존처럼 UA만 나간다.
DRAFT_FETCH_CONTACT = load_draft_fetch_contact()
# discover_drafts 관리 명령의 게이트. 운영자가 켜기 전까지는 크롤링하지 않는다.
DRAFT_DISCOVERY_ENABLED = load_draft_discovery_enabled()
# discover_drafts 한 번 실행에서 모든 소스를 합쳐 생성할 수 있는 최대
# 신규 드래프트 수. 아래 소스별 조회 상한과는 별개다.
DRAFT_DISCOVERY_MAX_PER_RUN = 10
# 소스별 조회 *시도* 상한(robots 확인 + create_draft_from_url 호출). 빈
# 결과나 중복만 나오는 소스가 위 생성 상한을 채우려 끝없이 재시도하는
# 것을 막는다.
DRAFT_DISCOVERY_MAX_FETCHES_PER_SOURCE = 20
# 스태프 대시보드 신선도 기준: last_checked_at이 이보다 오래됐거나 아직
# None인 활성 DraftSource는 "정체"로 표시한다. 48시간이면 하루치 실행을
# 몇 번 놓쳐도 바로 문제로 보이지 않을 여유를 준다.
DRAFT_SOURCE_STALE_HOURS = 48
# 러너 API 인증 토큰. 기본 빈 값 = 러너 경계 비활성(IsDiscoveryRunner가 빈 값이면 명시 거부).
DRAFT_DISCOVERY_RUNNER_TOKEN = _get_env("DRAFT_DISCOVERY_RUNNER_TOKEN")
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
    "django.contrib.sitemaps",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "drf_spectacular_sidecar",
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
    "web",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.gzip.GZipMiddleware",
    # 수집된 정적 파일을 앱 프로세스에서 바로 서빙한다 — 초기 배포에서 별도
    # 정적 파일 서버/CDN이 필요 없다. whitenoise 문서 권장대로
    # SecurityMiddleware 바로 다음(GZipMiddleware 바로 뒤)에 둬야 한다.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # AxesMiddleware는 인증이 끝난 뒤 잠금 응답을 렌더링해야 하므로 맨 마지막에 둔다.
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
                "core.context_processors.email_delivery_enabled",
                "core.context_processors.shell_css_bundled",
                "core.context_processors.font_preload_chunks",
                "core.context_processors.canonical_url",
                "core.context_processors.google_site_verification",
                "core.context_processors.ga_measurement_id",
                "staff.context_processors.sidebar_badge_counts",
                "staff.context_processors.staff_search_box",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {"default": load_database_config()}

# gunicorn은 워커 프로세스를 여러 개 띄우는데, 기본 LocMemCache는 프로세스별로
# 따로 있어 레이트리밋(allauth ACCOUNT_RATE_LIMITS, accounts.views 삭제
# 시도 잠금)이 워커마다, 재배포마다 조용히 초기화된다. DatabaseCache는
# 이미 있는 Postgres를 그대로 써서(새 서비스 불필요) 모든 워커·재배포가
# 공유한다. env 게이트 없이 항상 적용해 개발/테스트와 운영이 같은
# 백엔드를 쓰고 "django_cache" 테이블(core 마이그레이션이 생성)이 항상
# 실제로 사용되게 한다.
# allauth 레이트리밋 4종 + DRF 스로틀 8스코프 + 계정 삭제 잠금 카운터가
# 이 캐시 하나를 공유한다. 기본 MAX_ENTRIES(300)면 컬링(알파벳순 1/3 삭제)이
# 자주 일어나 살아 있는 카운터가 조기 소멸한다.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
        "OPTIONS": {"MAX_ENTRIES": 10000},
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
    # AxesStandaloneBackend는 반드시 첫 번째여야 한다 — 자격 증명 검증 없이
    # IP가 잠긴 경우 PermissionDenied로 인증을 즉시 중단시킨다.
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/collection/"
LOGOUT_REDIRECT_URL = "/"

# django-allauth: 이메일만을 식별자로 쓰고, 로그인 전 인증 메일 확인을 필수로 한다.
# ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION은 기존 "가입 즉시 자동 로그인" 정책을
# 대체한다 — 세션은 확인 링크를 클릭해야만 발급된다.
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_EMAIL_CONFIRMATION_EXPIRE_DAYS = 3
# 다중 이메일 UI 대신 단일 이메일 교체 흐름을 쓴다 — allauth가
# account/email_change.html을 찾게 된다.
ACCOUNT_CHANGE_EMAIL = True
# 커스텀 가입 폼(accounts/forms.py)이 allauth 기본 이메일/비밀번호 필드에
# 약관·개인정보 동의 체크박스를 추가한다. add_email은 현재 비밀번호
# 재확인을 추가한 EmailChangeForm으로 교체.
ACCOUNT_FORMS = {
    "signup": "accounts.forms.SignupForm",
    "add_email": "accounts.forms.EmailChangeForm",
}

# django-allauth socialaccount: 구글 로그인. 자격 증명은 env로만 받고(절대
# 커밋 금지), Google Cloud Console의 OAuth 클라이언트에 리디렉션 URI
# /accounts/google/login/callback/를 등록한다(개발은 localhost, 운영은
# 실제 호스트). env가 비어 있으면 자격 증명이 설정될 때까지 버튼이
# 숨겨진다(core.context_processors.google_oauth_configured 참고).
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
# 구글은 이메일 소유권을 검증하므로 신뢰할 수 있다: 검증된 구글 이메일이
# 기존 로컬 계정과 일치하면 그 계정으로 로그인시키고 구글 계정을 연결한다.
# 이게 안전한 건 구글이 완전히 신뢰되는 제공자이기 때문이다 — 신뢰도가
# 낮은 다른 제공자를 추가한다면 이 판단을 다시 검토해야 한다.
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

# 소셜 가입도 일반 가입과 같은 약관 동의를 강제한다(accounts/forms.py의
# SocialSignupForm). AUTO_SIGNUP 기본값(true)이면 신규 소셜 유저가 가입
# 폼을 건너뛰어 동의 없는 계정이 생기므로 반드시 False로 둔다(B2).
SOCIALACCOUNT_FORMS = {"signup": "accounts.forms.SocialSignupForm"}
SOCIALACCOUNT_AUTO_SIGNUP = False

# 인증 엔드포인트 속도 제한(무차별 대입·가입 폭주 방어). allauth는 이미
# 합리적인 기본값을 쓰고 있고 이 dict는 그 기본값 위에 병합된다(allauth:
# `ret.update(rls)`). 즉 여기 없는 동작은 allauth 기본값을 그대로 쓴다.
# 감사 가능하도록 보안상 중요한 항목만 명시하고, 공개 배포를 위해
# `signup`은 더 좁혔다. 형식은 "<횟수>/<기간>/<범위>"이며 범위는
# ip|key|user, 콤마로 여러 창을 연결하면 전부 통과해야 한다.
#   - signup: IP당 분당 5회 버스트 + 시간당 30회 지속(기본값은 더 느슨한 20/m/ip)
#   - login_failed: IP당 분당 10회 + 계정당 5분에 5회. 계정별 한도를 다
#     쓰면 쿨다운이 끝날 때까지 올바른 비밀번호로도 로그인 폼이 막힌다.
#     지속적인 IP 잠금은 axes가 별도로 담당한다.
#   - reset_password: 비밀번호 재설정 메일 요청 속도 제한(allauth 기본값).
# 속도 제한에 걸리면 templates/429.html이 렌더링된다.
#   - manage_email: 이메일 변경(/accounts/email/)에 현재 비밀번호 재확인이
#     새로 생겨 allauth 기본 10/m/user(느슨한 롤링 제한)보다 좁게 고정한다.
ACCOUNT_RATE_LIMITS = {
    "signup": "5/m/ip,30/h/ip",
    "login_failed": "10/m/ip,5/300s/key",
    "reset_password": "20/m/ip,5/m/key",
    "manage_email": "5/m/user,20/h/user",
}

# django-axes: allauth의 창 단위 속도 제한 위에 지속적인 무차별 대입 잠금을
# 더한다. allauth는 롤링 윈도 안에서만 인증을 막지만, axes는 쿨다운이 있는
# 하드 잠금을 추가해 반복 공격자를 완전히 차단하고 관리자
# 화면(AccessAttempt/AccessLog)에서 볼 수 있게 한다. IP로만 잠그는 이유는
# 사용자명으로 잠그면 공격자가 피해자를 잠글 수 있기 때문이며(DoS),
# 계정 단위 방어는 이미 allauth의 login_failed `key` 제한이 맡고 있다.
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 1  # 시간
AXES_LOCKOUT_PARAMETERS = ["ip_address"]
AXES_RESET_ON_SUCCESS = True
AXES_HTTP_RESPONSE_CODE = 429
AXES_LOCKOUT_TEMPLATE = "account/lockout.html"
# allauth는 식별자를 "login"이라는 폼 필드로 보낸다. axes도 같은 필드를
# 읽어야 올바른 자격 증명에 시도 기록을 남긴다.
AXES_USERNAME_FORM_FIELD = "login"
# 배포 시 주의: 리버스 프록시 뒤라면 TRUSTED_PROXY_COUNT env를 실제 프록시
# 홉 수로 설정해야 axes가 프록시 IP가 아닌 진짜 공격자 IP를 잠근다(안
# 하면 모든 사용자가 잠길 수 있다). 이 값이 AXES_CLIENT_IP_CALLABLE을
# core.ip.get_client_ip로 연결한다. TRUSTED_PROXY_COUNT가 없으면 axes 자체
# REMOTE_ADDR 기본값을 유지한다(django-axes의 AXES_IPWARE_* 설정을 여기서
# 쓰지 않는 이유는 core/ip.py 참고 — 이 프로젝트는 django-ipware에 의존하지 않는다).
TRUSTED_PROXY_COUNT = load_trusted_proxy_count()
AXES_CLIENT_IP_CALLABLE = build_axes_client_ip_callable(TRUSTED_PROXY_COUNT)

# 보안 쿠키: 개발(http)에서는 꺼져 있고, SECURE_COOKIES env를 설정하면 켜진다.
_secure_cookies = os.environ.get("SECURE_COOKIES", "").lower() in ("1", "true", "yes")
SESSION_COOKIE_SECURE = _secure_cookies
CSRF_COOKIE_SECURE = _secure_cookies
# JS 레이어가 csrftoken 쿠키를 읽어야 하므로 CSRF_COOKIE_HTTPONLY는 False로 둔다.
CSRF_COOKIE_HTTPONLY = False

# 프록시/HTTPS 보안 헤더: TLS 종료 리버스 프록시 뒤에 배포할 때 SECURE_SSL
# env로 선택적으로 켠다. 위 SECURE_COOKIES와는 독립적이라 재사용하지 않고
# 별도 플래그로 둔다.
SECURE_SSL = load_secure_ssl()
_secure_ssl_settings = build_secure_ssl_settings(SECURE_SSL)
if _secure_ssl_settings:
    SECURE_PROXY_SSL_HEADER = _secure_ssl_settings["SECURE_PROXY_SSL_HEADER"]
    SECURE_SSL_REDIRECT = _secure_ssl_settings["SECURE_SSL_REDIRECT"]
    SECURE_HSTS_SECONDS = _secure_ssl_settings["SECURE_HSTS_SECONDS"]
    SECURE_HSTS_INCLUDE_SUBDOMAINS = _secure_ssl_settings["SECURE_HSTS_INCLUDE_SUBDOMAINS"]
    SECURE_HSTS_PRELOAD = _secure_ssl_settings["SECURE_HSTS_PRELOAD"]

# 이메일(django-allauth 인증/비밀번호 재설정용). EMAIL_HOST가 비어 있으면
# 콘솔 백엔드로 대체돼 로컬 개발에서 실제 SMTP 자격 증명이 필요 없다.
EMAIL_HOST = _get_env("EMAIL_HOST")
EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend"
    if EMAIL_HOST
    else "django.core.mail.backends.console.EmailBackend"
)
EMAIL_PORT = load_email_port()
EMAIL_HOST_USER = _get_env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = _get_env("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = _get_env("EMAIL_USE_TLS", "true").lower() in ("1", "true", "yes")
DEFAULT_FROM_EMAIL = _get_env("DEFAULT_FROM_EMAIL", "no-reply@takulife.example")
# 법적 고지 페이지/푸터에 표시하는 문의·개인정보 권리 요청 연락처. 실제
# 지원 메일함이 준비되기 전까지의 임시 도메인이다 — 실제 주소가 생기면
# 코드 변경 없이 env만 바꾸면 된다.
SUPPORT_EMAIL = _get_env("SUPPORT_EMAIL", "support@takulife.example")

# 구글 서치 콘솔 소유 확인 토큰과 GA4 측정 ID(G-로 시작). 비어 있으면
# 해당 태그가 아예 렌더되지 않아 로컬·미설정 환경에는 추적이 없다.
GOOGLE_SITE_VERIFICATION = _get_env("GOOGLE_SITE_VERIFICATION")
GA_MEASUREMENT_ID = _get_env("GA_MEASUREMENT_ID")

# DRF: 공식 제보(promotion) 속도를 제한해 인증된 사용자가 승격된
# PersonalEntry 드래프트로 관리자 검토 큐를 채우지 못하게 한다.
# 뷰 단위(PromotePersonalEntryView)로만 적용돼 다른 엔드포인트는
# 영향받지 않는다. collection_item_create / visit_record_create /
# personal_entry_create는 수동 폼으로는 분당 30회에 절대 도달할 수
# 없다 — 이 상한은 정상 사용이 아니라 bfcache식 중복 제출 폭주와
# 스팸을 막기 위한 것이다. event_interest_create / user_event_status_create는
# 목록에서 여러 행사를 빠르게 연달아 누를 수 있어 분당 60회로 더 넉넉히
# 잡았다. visit_record_photo_create는 기록당 사진 5장 상한이 이미 있어
# 30/minute으로도 여러 기록에 걸친 정상 업로드를 막지 않는다.
REST_FRAMEWORK = {
    # 세션 인증만 쓴다 — 이 앱은 브라우저/세션 기반이다. DRF 기본
    # BasicAuthentication을 빼는 이유는 CSRF 우회 구멍을 막기 위해서다:
    # Basic 인증 요청은 CSRF 검사를 건너뛰므로, 위조된 크로스사이트
    # 요청으로 스태프 자격 증명이 데이터를 변경할 수 있다.
    # SessionAuthentication은 안전하지 않은 메서드에 CSRF를 강제한다.
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_RATES": {
        "promotion": "20/day",
        "collection_item_create": "30/minute",
        "visit_record_create": "30/minute",
        "personal_entry_create": "30/minute",
        "event_interest_create": "60/minute",
        "user_event_status_create": "60/minute",
        "visit_record_photo_create": "30/minute",
        "discovery_runner": "60/minute",
    },
}

SPECTACULAR_SETTINGS = {
    "TITLE": "takulife API",
    "DESCRIPTION": "서브컬처 팬을 위한 개인 굿즈 컬렉션 서비스 takulife의 세션 인증 기반 API.",
    "VERSION": "0.1.0",
    # 외부 CDN 대신 로컬 정적 파일로 Swagger UI 자산을 서빙한다(비용·오프라인 규약).
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "SERVE_INCLUDE_SCHEMA": False,
    "PREPROCESSING_HOOKS": ["config.openapi.preprocess_exclude_non_api_paths"],
    "TAGS": [
        {"name": "core", "description": "상태 확인·인증 세션"},
        {"name": "events", "description": "공개 행사 카탈로그"},
        {"name": "drafts", "description": "스태프 전용 행사 드래프트 수집·검토"},
        {"name": "archive", "description": "행사 상태·다녀온 기록·관심"},
        {"name": "collection", "description": "굿즈 컬렉션·비공식 기록"},
    ],
}

# 콘솔(stdout) 로깅. PaaS 플랫폼이 stdout을 수집하는 배포 방식에 맞춘
# 것으로 파일 핸들러도, 외부 로그 서비스도 두지 않는다. django와 root는
# 기본 INFO, django.request만 ERROR로 올려서 처리되지 않은 5xx 예외는
# 스택 트레이스와 함께 출력하되 요청마다 나오는 Django 자체 INFO/WARNING
# 잡음(404 등)은 찍히지 않게 한다.
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
