import importlib

import pytest
from django.core.exceptions import ImproperlyConfigured

pytestmark = pytest.mark.contract


def test_SECRET_KEY가_미설정이면_env_파일에서_값을_읽어온다(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SECRET_KEY=loaded-from-env-file\n", encoding="utf-8")

    monkeypatch.delenv("SECRET_KEY", raising=False)

    settings_module = importlib.import_module("config.settings")
    monkeypatch.setattr(settings_module, "BASE_DIR", tmp_path)

    assert settings_module.load_secret_key(debug=True) == "loaded-from-env-file"


def test_ANTHROPIC_API_KEY가_미설정이면_env_파일에서_값을_읽어온다(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("ANTHROPIC_API_KEY=loaded-anthropic-key\n", encoding="utf-8")

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    settings_module = importlib.import_module("config.settings")
    monkeypatch.setattr(settings_module, "BASE_DIR", tmp_path)

    assert settings_module.load_anthropic_api_key() == "loaded-anthropic-key"


def test_DATABASE_URL이_미설정이면_sqlite로_대체된다(monkeypatch, tmp_path):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    settings_module = importlib.import_module("config.settings")
    monkeypatch.setattr(settings_module, "BASE_DIR", tmp_path)

    config = settings_module.load_database_config()

    assert config == {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": tmp_path / "db.sqlite3",
    }


def test_DATABASE_URL이_postgres_스킴이면_접속_정보를_파싱한다(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://taku:taku@localhost:5432/taku"
    )

    settings_module = importlib.import_module("config.settings")

    config = settings_module.load_database_config()

    assert config["ENGINE"] == "django.db.backends.postgresql"
    assert config["NAME"] == "taku"
    assert config["USER"] == "taku"
    assert config["PASSWORD"] == "taku"
    assert config["HOST"] == "localhost"
    assert config["PORT"] == 5432


def test_DATABASE_URL에_포트가_없으면_빈_문자열로_남는다(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://taku:taku@localhost/taku")

    settings_module = importlib.import_module("config.settings")

    config = settings_module.load_database_config()

    # URL에 포트가 없으면 dj-database-url은 PORT를 빈 채로 둔다. 이후
    # Django/psycopg가 Postgres 자체 기본 포트(5432)로 대체한다.
    assert config["PORT"] == ""


def test_DATABASE_URL_비밀번호의_URL_인코딩_특수문자를_복원한다(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://taku:p%40ss%23word@localhost:5432/taku"
    )

    settings_module = importlib.import_module("config.settings")

    config = settings_module.load_database_config()

    assert config["PASSWORD"] == "p@ss#word"


def test_DATABASE_URL_스킴을_알_수_없으면_예외를_발생시킨다(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "mysql://taku:taku@localhost:3306/taku")

    settings_module = importlib.import_module("config.settings")

    with pytest.raises(ValueError):
        settings_module.load_database_config()


def test_DATABASE_URL의_sslmode_쿼리파라미터를_OPTIONS에_반영한다(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://taku:taku@localhost:5432/taku?sslmode=require",
    )

    settings_module = importlib.import_module("config.settings")

    config = settings_module.load_database_config()

    assert config["OPTIONS"] == {"sslmode": "require"}


def test_DEBUG가_미설정이면_기본값_True를_사용한다(monkeypatch):
    monkeypatch.delenv("DEBUG", raising=False)

    settings_module = importlib.import_module("config.settings")

    assert settings_module.load_debug() is True


def test_DEBUG_환경변수가_false이면_False로_해석한다(monkeypatch):
    monkeypatch.setenv("DEBUG", "false")

    settings_module = importlib.import_module("config.settings")

    assert settings_module.load_debug() is False


# ---------------------------------------------------------------------------
# 설정값 프로덕션 강화
# (.docs/plans/2026-07-14-stage0-deployment-foundation-plan.md §8)
# ---------------------------------------------------------------------------


def test_DEBUG_False에서_SECRET_KEY가_없으면_예외를_발생시킨다(monkeypatch):
    # 빈 문자열(delenv가 아니라)을 써야 _get_env의 .env 파일 폴백을 끊어서,
    # 개발자의 실제 .env 내용과 무관하게 이 테스트가 독립적으로 동작한다.
    monkeypatch.setenv("SECRET_KEY", "")

    settings_module = importlib.import_module("config.settings")

    with pytest.raises(ImproperlyConfigured):
        settings_module.load_secret_key(debug=False)


def test_DEBUG_True에서_SECRET_KEY가_없으면_개발용_기본키를_사용한다(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "")

    settings_module = importlib.import_module("config.settings")

    assert (
        settings_module.load_secret_key(debug=True)
        == "django-insecure-local-dev-key-change-me"
    )


def test_SECRET_KEY가_설정되어_있으면_DEBUG값과_무관하게_그대로_사용한다(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "from-env")

    settings_module = importlib.import_module("config.settings")

    assert settings_module.load_secret_key(debug=False) == "from-env"


def test_ALLOWED_HOSTS가_미설정이면_빈_리스트를_반환한다(monkeypatch, tmp_path):
    monkeypatch.delenv("ALLOWED_HOSTS", raising=False)

    settings_module = importlib.import_module("config.settings")
    monkeypatch.setattr(settings_module, "BASE_DIR", tmp_path)

    assert settings_module.load_allowed_hosts() == []


def test_ALLOWED_HOSTS_콤마로_구분된_값을_리스트로_파싱한다(monkeypatch):
    monkeypatch.setenv(
        "ALLOWED_HOSTS", "takulife.kr, www.takulife.kr ,api.takulife.kr"
    )

    settings_module = importlib.import_module("config.settings")

    assert settings_module.load_allowed_hosts() == [
        "takulife.kr",
        "www.takulife.kr",
        "api.takulife.kr",
    ]


def test_CSRF_TRUSTED_ORIGINS가_미설정이면_빈_리스트를_반환한다(monkeypatch, tmp_path):
    monkeypatch.delenv("CSRF_TRUSTED_ORIGINS", raising=False)

    settings_module = importlib.import_module("config.settings")
    monkeypatch.setattr(settings_module, "BASE_DIR", tmp_path)

    assert settings_module.load_csrf_trusted_origins() == []


def test_CSRF_TRUSTED_ORIGINS_콤마로_구분된_값을_리스트로_파싱한다(monkeypatch):
    monkeypatch.setenv(
        "CSRF_TRUSTED_ORIGINS", "https://takulife.kr,https://www.takulife.kr"
    )

    settings_module = importlib.import_module("config.settings")

    assert settings_module.load_csrf_trusted_origins() == [
        "https://takulife.kr",
        "https://www.takulife.kr",
    ]


def test_SECURE_SSL이_미설정이면_False가_기본값이다(monkeypatch, tmp_path):
    monkeypatch.delenv("SECURE_SSL", raising=False)

    settings_module = importlib.import_module("config.settings")
    monkeypatch.setattr(settings_module, "BASE_DIR", tmp_path)

    assert settings_module.load_secure_ssl() is False


def test_SECURE_SSL_환경변수가_true이면_True로_해석한다(monkeypatch):
    monkeypatch.setenv("SECURE_SSL", "true")

    settings_module = importlib.import_module("config.settings")

    assert settings_module.load_secure_ssl() is True


def test_SECURE_SSL이_꺼져있으면_보안_설정을_추가하지_않는다():
    settings_module = importlib.import_module("config.settings")

    assert settings_module.build_secure_ssl_settings(False) == {}


def test_SECURE_SSL이_켜지면_프록시와_HSTS_설정을_구성한다():
    settings_module = importlib.import_module("config.settings")

    result = settings_module.build_secure_ssl_settings(True)

    assert result == {
        "SECURE_PROXY_SSL_HEADER": ("HTTP_X_FORWARDED_PROTO", "https"),
        "SECURE_SSL_REDIRECT": True,
        "SECURE_HSTS_SECONDS": 31536000,
        "SECURE_HSTS_INCLUDE_SUBDOMAINS": True,
        "SECURE_HSTS_PRELOAD": False,
    }


def test_설정_모듈은_STATIC_ROOT를_BASE_DIR_하위_staticfiles로_정의한다():
    settings_module = importlib.import_module("config.settings")

    assert settings_module.STATIC_ROOT == settings_module.BASE_DIR / "staticfiles"


def test_DEBUG_모드에서는_일반_정적파일_스토리지를_사용한다():
    """DEBUG=true(로컬 개발/테스트 설정)는 whitenoise의 매니페스트 스토리지를
    쓰면 안 된다 — 그 백엔드는 collectstatic이 먼저 실행돼(staticfiles.json)
    있어야 하는데, 로컬 개발/테스트는 그걸 절대 하지 않는다. DEBUG에서
    일반 파일시스템 스토리지를 쓰면 빌드 단계 없이도 {% static %}이 그대로
    풀린다 — whitenoise 도입 전 동작과 정확히 같다."""
    settings_module = importlib.import_module("config.settings")

    assert settings_module.DEBUG is True
    assert (
        settings_module.STORAGES["staticfiles"]["BACKEND"]
        == "django.contrib.staticfiles.storage.StaticFilesStorage"
    )


def test_whitenoise_미들웨어는_SecurityMiddleware_바로_다음에_등록된다():
    settings_module = importlib.import_module("config.settings")

    middleware = settings_module.MIDDLEWARE
    security_index = middleware.index("django.middleware.security.SecurityMiddleware")

    assert middleware[security_index + 1] == "whitenoise.middleware.WhiteNoiseMiddleware"


def test_설정_모듈은_콘솔_로깅_핸들러를_정의한다():
    settings_module = importlib.import_module("config.settings")

    logging_config = settings_module.LOGGING

    assert logging_config["handlers"]["console"]["class"] == "logging.StreamHandler"
    assert logging_config["root"]["level"] == "INFO"
    assert logging_config["loggers"]["django.request"]["level"] == "ERROR"


# ---------------------------------------------------------------------------
# 보안 게이트 후속 조치: DEBUG fail-open 방어(H1)
# ---------------------------------------------------------------------------


def test_DEBUG_True에서_ALLOWED_HOSTS가_설정되어_있으면_예외를_발생시킨다():
    """H1: DEBUG=false를 깜빡한 것만으로 SECRET_KEY 하드 실패를 조용히
    우회해서 실제 도메인에 디버그 페이지와 안전하지 않은 개발용 키를 그대로
    노출하면 안 된다. ALLOWED_HOSTS가 설정돼 있다는 것 자체가 명백한
    프로덕션 신호다 — 로컬 개발에서는 그걸 설정할 이유가 없다."""
    settings_module = importlib.import_module("config.settings")

    with pytest.raises(ImproperlyConfigured):
        settings_module.guard_debug_allowed_hosts(
            debug=True, allowed_hosts=["takulife.kr"]
        )


def test_DEBUG_True이고_ALLOWED_HOSTS가_비어있으면_통과한다():
    settings_module = importlib.import_module("config.settings")

    # 예외를 던지면 안 된다 — 이것이 로컬 개발 기본값이다.
    settings_module.guard_debug_allowed_hosts(debug=True, allowed_hosts=[])


def test_DEBUG_False이고_ALLOWED_HOSTS가_설정되어_있으면_통과한다():
    settings_module = importlib.import_module("config.settings")

    # 예외를 던지면 안 된다 — 이것이 의도된 프로덕션 설정이다.
    settings_module.guard_debug_allowed_hosts(
        debug=False, allowed_hosts=["takulife.kr"]
    )


def test_설정_모듈의_ALLOWED_HOSTS_속성은_load_allowed_hosts_결과와_일치한다():
    settings_module = importlib.import_module("config.settings")

    assert settings_module.ALLOWED_HOSTS == settings_module.load_allowed_hosts()


def test_설정_모듈의_CSRF_TRUSTED_ORIGINS_속성은_load_csrf_trusted_origins_결과와_일치한다():
    settings_module = importlib.import_module("config.settings")

    assert (
        settings_module.CSRF_TRUSTED_ORIGINS
        == settings_module.load_csrf_trusted_origins()
    )


# ---------------------------------------------------------------------------
# STORAGES.staticfiles 분기를 다른 load_* 함수들과 같은 패턴으로 테스트
# 가능한 순수 함수로 뽑아낸 부분
# ---------------------------------------------------------------------------


def test_DEBUG_True이면_일반_정적파일_스토리지_경로를_반환한다():
    settings_module = importlib.import_module("config.settings")

    assert (
        settings_module.load_staticfiles_storage(True)
        == "django.contrib.staticfiles.storage.StaticFilesStorage"
    )


def test_DEBUG_False이면_whitenoise_매니페스트_스토리지_경로를_반환한다():
    settings_module = importlib.import_module("config.settings")

    assert (
        settings_module.load_staticfiles_storage(False)
        == "whitenoise.storage.CompressedManifestStaticFilesStorage"
    )


# ---------------------------------------------------------------------------
# 미디어 스토리지 백엔드 env 게이트(오브젝트 스토리지)
# ---------------------------------------------------------------------------


def test_MEDIA_STORAGE_BUCKET이_미설정이면_파일시스템_스토리지로_대체된다(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("MEDIA_STORAGE_BUCKET", raising=False)

    settings_module = importlib.import_module("config.settings")
    monkeypatch.setattr(settings_module, "BASE_DIR", tmp_path)

    assert settings_module.load_media_storage_config() == {
        "BACKEND": "django.core.files.storage.FileSystemStorage"
    }


def test_MEDIA_STORAGE_BUCKET이_설정되면_S3_백엔드_설정을_반환한다(monkeypatch):
    monkeypatch.setenv("MEDIA_STORAGE_BUCKET", "takulife-media")
    monkeypatch.setenv("MEDIA_STORAGE_ACCESS_KEY_ID", "key-id")
    monkeypatch.setenv("MEDIA_STORAGE_SECRET_ACCESS_KEY", "secret")
    monkeypatch.setenv(
        "MEDIA_STORAGE_ENDPOINT_URL", "https://example.r2.cloudflarestorage.com"
    )
    monkeypatch.setenv("MEDIA_STORAGE_REGION", "auto")

    settings_module = importlib.import_module("config.settings")

    assert settings_module.load_media_storage_config() == {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
        "OPTIONS": {
            "bucket_name": "takulife-media",
            "access_key": "key-id",
            "secret_key": "secret",
            "endpoint_url": "https://example.r2.cloudflarestorage.com",
            "region_name": "auto",
        },
    }


def test_MEDIA_STORAGE_BUCKET은_있는데_SECRET_ACCESS_KEY가_없으면_예외를_발생시킨다(
    monkeypatch,
):
    monkeypatch.setenv("MEDIA_STORAGE_BUCKET", "takulife-media")
    monkeypatch.setenv("MEDIA_STORAGE_ACCESS_KEY_ID", "key-id")
    # 빈 문자열(delenv가 아니라)을 써야 _get_env의 .env 파일 폴백을 끊는다 —
    # 위 load_secret_key 하드 실패 테스트와 같은 패턴이다.
    monkeypatch.setenv("MEDIA_STORAGE_SECRET_ACCESS_KEY", "")
    monkeypatch.setenv(
        "MEDIA_STORAGE_ENDPOINT_URL", "https://example.r2.cloudflarestorage.com"
    )

    settings_module = importlib.import_module("config.settings")

    with pytest.raises(ImproperlyConfigured):
        settings_module.load_media_storage_config()


# ---------------------------------------------------------------------------
# 프록시를 고려한 클라이언트 IP 판정
# (.docs/plans/2026-07-14-stage0-deployment-foundation-plan.md §8)
# ---------------------------------------------------------------------------


def test_TRUSTED_PROXY_COUNT가_미설정이면_None을_반환한다(monkeypatch, tmp_path):
    monkeypatch.delenv("TRUSTED_PROXY_COUNT", raising=False)

    settings_module = importlib.import_module("config.settings")
    monkeypatch.setattr(settings_module, "BASE_DIR", tmp_path)

    assert settings_module.load_trusted_proxy_count() is None


def test_TRUSTED_PROXY_COUNT_환경변수를_정수로_파싱한다(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_COUNT", "1")

    settings_module = importlib.import_module("config.settings")

    assert settings_module.load_trusted_proxy_count() == 1


def test_TRUSTED_PROXY_COUNT가_정수가_아니면_예외를_발생시킨다(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_COUNT", "abc")

    settings_module = importlib.import_module("config.settings")

    with pytest.raises(ImproperlyConfigured):
        settings_module.load_trusted_proxy_count()


def test_TRUSTED_PROXY_COUNT가_음수이면_예외를_발생시킨다(monkeypatch):
    """음수 개수를 허용하면 resolve_client_ip의
    hops[-trusted_proxy_count]가 양수 인덱스가 되어, X-Forwarded-For의
    신뢰할 수 있는 오른쪽 끝 대신 공격자가 조작 가능한 왼쪽 끝을 신뢰하게
    된다 — 스푸핑 방어가 완전히 무력화된다."""
    monkeypatch.setenv("TRUSTED_PROXY_COUNT", "-1")

    settings_module = importlib.import_module("config.settings")

    with pytest.raises(ImproperlyConfigured):
        settings_module.load_trusted_proxy_count()


def test_TRUSTED_PROXY_COUNT가_없으면_axes_클라이언트_IP_콜백을_비운다():
    settings_module = importlib.import_module("config.settings")

    assert settings_module.build_axes_client_ip_callable(None) is None
    assert settings_module.build_axes_client_ip_callable(0) is None


def test_TRUSTED_PROXY_COUNT가_설정되면_core_ip_경로를_axes_클라이언트_IP_콜백으로_사용한다():
    settings_module = importlib.import_module("config.settings")

    assert (
        settings_module.build_axes_client_ip_callable(1) == "core.ip.get_client_ip"
    )


def test_설정_모듈의_AXES_CLIENT_IP_CALLABLE_속성은_build_axes_client_ip_callable_결과와_일치한다():
    settings_module = importlib.import_module("config.settings")

    assert settings_module.AXES_CLIENT_IP_CALLABLE == (
        settings_module.build_axes_client_ip_callable(
            settings_module.TRUSTED_PROXY_COUNT
        )
    )


# ---------------------------------------------------------------------------
# 공유 캐시 백엔드(G11)
# (.docs/plans/2026-07-14-stage0-deployment-foundation-plan.md §8)
# ---------------------------------------------------------------------------


def test_설정_모듈은_DatabaseCache_백엔드를_기본_캐시로_사용한다():
    settings_module = importlib.import_module("config.settings")

    assert settings_module.CACHES["default"] == {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
    }


# ---------------------------------------------------------------------------
# 드래프트 자동 수집 기능 플래그(F6)
# ---------------------------------------------------------------------------


def test_DRAFT_DISCOVERY_ENABLED가_미설정이면_기본값_False를_사용한다(monkeypatch, tmp_path):
    monkeypatch.delenv("DRAFT_DISCOVERY_ENABLED", raising=False)

    settings_module = importlib.import_module("config.settings")
    monkeypatch.setattr(settings_module, "BASE_DIR", tmp_path)

    assert settings_module.load_draft_discovery_enabled() is False


def test_DRAFT_DISCOVERY_ENABLED_환경변수가_true이면_True로_해석한다(monkeypatch):
    monkeypatch.setenv("DRAFT_DISCOVERY_ENABLED", "true")

    settings_module = importlib.import_module("config.settings")

    assert settings_module.load_draft_discovery_enabled() is True


# ---------------------------------------------------------------------------
# 드래프트 자동 수집 연락처(DRAFT_FETCH_CONTACT)
# ---------------------------------------------------------------------------


def test_DRAFT_FETCH_CONTACT_환경변수가_설정되면_그_값을_읽어온다(monkeypatch):
    monkeypatch.setenv("DRAFT_FETCH_CONTACT", "https://example.com/about")

    settings_module = importlib.import_module("config.settings")

    assert (
        settings_module.load_draft_fetch_contact()
        == "https://example.com/about"
    )


def test_설정_모듈의_DRAFT_FETCH_CONTACT_속성은_load_draft_fetch_contact_결과와_일치한다():
    # env 미설정 환경에서는 양쪽 다 ""로 우연히 같아질 수 있어 이 테스트만으로는
    # 결함을 못 잡을 수 있다 — 주 증거는 위 env 주입 테스트다.
    settings_module = importlib.import_module("config.settings")

    assert (
        settings_module.DRAFT_FETCH_CONTACT
        == settings_module.load_draft_fetch_contact()
    )


# ---------------------------------------------------------------------------
# EMAIL_PORT 정수 캐스팅 가드(S3)
# ---------------------------------------------------------------------------


def test_EMAIL_PORT가_미설정이면_기본값_587을_반환한다(monkeypatch, tmp_path):
    monkeypatch.delenv("EMAIL_PORT", raising=False)

    settings_module = importlib.import_module("config.settings")
    monkeypatch.setattr(settings_module, "BASE_DIR", tmp_path)

    assert settings_module.load_email_port() == 587


def test_EMAIL_PORT_환경변수를_정수로_파싱한다(monkeypatch):
    monkeypatch.setenv("EMAIL_PORT", "25000")

    settings_module = importlib.import_module("config.settings")

    assert settings_module.load_email_port() == 25000


def test_EMAIL_PORT가_숫자가_아니면_ImproperlyConfigured를_발생시킨다(monkeypatch):
    monkeypatch.setenv("EMAIL_PORT", "abc")

    settings_module = importlib.import_module("config.settings")

    with pytest.raises(ImproperlyConfigured) as exc_info:
        settings_module.load_email_port()

    assert "EMAIL_PORT" in str(exc_info.value)
    assert "abc" in str(exc_info.value)
