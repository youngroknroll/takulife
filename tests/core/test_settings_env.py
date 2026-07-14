import importlib

import pytest
from django.core.exceptions import ImproperlyConfigured


def test_settings_load_secret_key_from_env_file(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("SECRET_KEY=loaded-from-env-file\n", encoding="utf-8")

    monkeypatch.delenv("SECRET_KEY", raising=False)

    settings_module = importlib.import_module("config.settings")
    monkeypatch.setattr(settings_module, "BASE_DIR", tmp_path)

    assert settings_module.load_secret_key(debug=True) == "loaded-from-env-file"


def test_settings_load_anthropic_api_key_from_env_file(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text("ANTHROPIC_API_KEY=loaded-anthropic-key\n", encoding="utf-8")

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    settings_module = importlib.import_module("config.settings")
    monkeypatch.setattr(settings_module, "BASE_DIR", tmp_path)

    assert settings_module.load_anthropic_api_key() == "loaded-anthropic-key"


def test_load_database_config_falls_back_to_sqlite_when_unset(monkeypatch, tmp_path):
    monkeypatch.delenv("DATABASE_URL", raising=False)

    settings_module = importlib.import_module("config.settings")
    monkeypatch.setattr(settings_module, "BASE_DIR", tmp_path)

    config = settings_module.load_database_config()

    assert config == {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": tmp_path / "db.sqlite3",
    }


def test_load_database_config_parses_postgres_url(monkeypatch):
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


def test_load_database_config_defaults_port_when_omitted(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgres://taku:taku@localhost/taku")

    settings_module = importlib.import_module("config.settings")

    config = settings_module.load_database_config()

    # dj-database-url leaves PORT empty when the URL omits it; Django/psycopg
    # then fall back to Postgres's own default port (5432).
    assert config["PORT"] == ""


def test_load_database_config_unquotes_special_characters_in_password(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://taku:p%40ss%23word@localhost:5432/taku"
    )

    settings_module = importlib.import_module("config.settings")

    config = settings_module.load_database_config()

    assert config["PASSWORD"] == "p@ss#word"


def test_load_database_config_raises_for_unknown_scheme(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "mysql://taku:taku@localhost:3306/taku")

    settings_module = importlib.import_module("config.settings")

    with pytest.raises(ValueError):
        settings_module.load_database_config()


def test_load_database_config_reflects_sslmode_query_param_in_options(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://taku:taku@localhost:5432/taku?sslmode=require",
    )

    settings_module = importlib.import_module("config.settings")

    config = settings_module.load_database_config()

    assert config["OPTIONS"] == {"sslmode": "require"}


def test_settings_debug_defaults_to_true_when_env_unset(monkeypatch):
    monkeypatch.delenv("DEBUG", raising=False)

    settings_module = importlib.import_module("config.settings")

    assert settings_module.load_debug() is True


def test_settings_debug_false_when_env_set_to_false(monkeypatch):
    monkeypatch.setenv("DEBUG", "false")

    settings_module = importlib.import_module("config.settings")

    assert settings_module.load_debug() is False


# ---------------------------------------------------------------------------
# PR-0a: settings production hardening
# (.docs/plans/2026-07-14-stage0-deployment-foundation-plan.md §8 PR-0a)
# ---------------------------------------------------------------------------


def test_load_secret_key_raises_when_debug_false_and_env_unset(monkeypatch):
    # Empty string (not delenv) short-circuits _get_env's .env-file fallback
    # so this test is independent of whatever the developer's real .env has.
    monkeypatch.setenv("SECRET_KEY", "")

    settings_module = importlib.import_module("config.settings")

    with pytest.raises(ImproperlyConfigured):
        settings_module.load_secret_key(debug=False)


def test_load_secret_key_uses_insecure_dev_fallback_when_debug_true(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "")

    settings_module = importlib.import_module("config.settings")

    assert (
        settings_module.load_secret_key(debug=True)
        == "django-insecure-local-dev-key-change-me"
    )


def test_load_secret_key_returns_env_value_regardless_of_debug(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "from-env")

    settings_module = importlib.import_module("config.settings")

    assert settings_module.load_secret_key(debug=False) == "from-env"


def test_load_allowed_hosts_defaults_to_empty_list_when_unset(monkeypatch, tmp_path):
    monkeypatch.delenv("ALLOWED_HOSTS", raising=False)

    settings_module = importlib.import_module("config.settings")
    monkeypatch.setattr(settings_module, "BASE_DIR", tmp_path)

    assert settings_module.load_allowed_hosts() == []


def test_load_allowed_hosts_parses_comma_separated_env(monkeypatch):
    monkeypatch.setenv(
        "ALLOWED_HOSTS", "takulife.kr, www.takulife.kr ,api.takulife.kr"
    )

    settings_module = importlib.import_module("config.settings")

    assert settings_module.load_allowed_hosts() == [
        "takulife.kr",
        "www.takulife.kr",
        "api.takulife.kr",
    ]


def test_load_csrf_trusted_origins_defaults_to_empty_list_when_unset(monkeypatch, tmp_path):
    monkeypatch.delenv("CSRF_TRUSTED_ORIGINS", raising=False)

    settings_module = importlib.import_module("config.settings")
    monkeypatch.setattr(settings_module, "BASE_DIR", tmp_path)

    assert settings_module.load_csrf_trusted_origins() == []


def test_load_csrf_trusted_origins_parses_comma_separated_env(monkeypatch):
    monkeypatch.setenv(
        "CSRF_TRUSTED_ORIGINS", "https://takulife.kr,https://www.takulife.kr"
    )

    settings_module = importlib.import_module("config.settings")

    assert settings_module.load_csrf_trusted_origins() == [
        "https://takulife.kr",
        "https://www.takulife.kr",
    ]


def test_load_secure_ssl_defaults_to_false_when_unset(monkeypatch, tmp_path):
    monkeypatch.delenv("SECURE_SSL", raising=False)

    settings_module = importlib.import_module("config.settings")
    monkeypatch.setattr(settings_module, "BASE_DIR", tmp_path)

    assert settings_module.load_secure_ssl() is False


def test_load_secure_ssl_true_when_env_set(monkeypatch):
    monkeypatch.setenv("SECURE_SSL", "true")

    settings_module = importlib.import_module("config.settings")

    assert settings_module.load_secure_ssl() is True


def test_build_secure_ssl_settings_empty_when_disabled():
    settings_module = importlib.import_module("config.settings")

    assert settings_module.build_secure_ssl_settings(False) == {}


def test_build_secure_ssl_settings_configures_proxy_and_hsts_when_enabled():
    settings_module = importlib.import_module("config.settings")

    result = settings_module.build_secure_ssl_settings(True)

    assert result == {
        "SECURE_PROXY_SSL_HEADER": ("HTTP_X_FORWARDED_PROTO", "https"),
        "SECURE_SSL_REDIRECT": True,
        "SECURE_HSTS_SECONDS": 31536000,
        "SECURE_HSTS_INCLUDE_SUBDOMAINS": True,
        "SECURE_HSTS_PRELOAD": False,
    }


def test_settings_module_defines_static_root():
    settings_module = importlib.import_module("config.settings")

    assert settings_module.STATIC_ROOT == settings_module.BASE_DIR / "staticfiles"


def test_settings_module_uses_plain_static_storage_in_debug_mode():
    """DEBUG=true (local dev / test settings) must not use whitenoise's
    manifest storage — that backend requires collectstatic to have run first
    (staticfiles.json), which local dev/test never does. Using the plain
    filesystem storage in DEBUG keeps {% static %} resolvable without a
    build step, matching current (pre-whitenoise) behavior exactly."""
    settings_module = importlib.import_module("config.settings")

    assert settings_module.DEBUG is True
    assert (
        settings_module.STORAGES["staticfiles"]["BACKEND"]
        == "django.contrib.staticfiles.storage.StaticFilesStorage"
    )


def test_settings_module_registers_whitenoise_middleware_after_security():
    settings_module = importlib.import_module("config.settings")

    middleware = settings_module.MIDDLEWARE
    security_index = middleware.index("django.middleware.security.SecurityMiddleware")

    assert middleware[security_index + 1] == "whitenoise.middleware.WhiteNoiseMiddleware"


def test_settings_module_defines_logging_console_handler():
    settings_module = importlib.import_module("config.settings")

    logging_config = settings_module.LOGGING

    assert logging_config["handlers"]["console"]["class"] == "logging.StreamHandler"
    assert logging_config["root"]["level"] == "INFO"
    assert logging_config["loggers"]["django.request"]["level"] == "ERROR"


# ---------------------------------------------------------------------------
# Security gate follow-up (2026-07-14): DEBUG fail-open defense (H1)
# ---------------------------------------------------------------------------


def test_guard_debug_allowed_hosts_raises_when_allowed_hosts_set_and_debug_true():
    """H1: forgetting DEBUG=false alone must not silently bypass the
    SECRET_KEY hard fail and serve a real domain with debug pages + the
    insecure dev key. ALLOWED_HOSTS set is an unambiguous production signal —
    local dev never has a reason to set it."""
    settings_module = importlib.import_module("config.settings")

    with pytest.raises(ImproperlyConfigured):
        settings_module.guard_debug_allowed_hosts(
            debug=True, allowed_hosts=["takulife.kr"]
        )


def test_guard_debug_allowed_hosts_allows_debug_true_when_allowed_hosts_empty():
    settings_module = importlib.import_module("config.settings")

    # Must not raise — this is the local dev default.
    settings_module.guard_debug_allowed_hosts(debug=True, allowed_hosts=[])


def test_guard_debug_allowed_hosts_allows_debug_false_when_allowed_hosts_set():
    settings_module = importlib.import_module("config.settings")

    # Must not raise — this is the intended production configuration.
    settings_module.guard_debug_allowed_hosts(
        debug=False, allowed_hosts=["takulife.kr"]
    )


def test_settings_module_wires_allowed_hosts_attribute():
    settings_module = importlib.import_module("config.settings")

    assert settings_module.ALLOWED_HOSTS == settings_module.load_allowed_hosts()


def test_settings_module_wires_csrf_trusted_origins_attribute():
    settings_module = importlib.import_module("config.settings")

    assert (
        settings_module.CSRF_TRUSTED_ORIGINS
        == settings_module.load_csrf_trusted_origins()
    )


# ---------------------------------------------------------------------------
# Code review follow-up (2026-07-14): extract STORAGES.staticfiles branch
# into a testable pure function, matching the load_* function pattern.
# ---------------------------------------------------------------------------


def test_load_staticfiles_storage_returns_plain_storage_when_debug_true():
    settings_module = importlib.import_module("config.settings")

    assert (
        settings_module.load_staticfiles_storage(True)
        == "django.contrib.staticfiles.storage.StaticFilesStorage"
    )


def test_load_staticfiles_storage_returns_whitenoise_manifest_when_debug_false():
    settings_module = importlib.import_module("config.settings")

    assert (
        settings_module.load_staticfiles_storage(False)
        == "whitenoise.storage.CompressedManifestStaticFilesStorage"
    )


# ---------------------------------------------------------------------------
# PR-0b checkpoint 2/3: media storage backend env gate (object storage)
# ---------------------------------------------------------------------------


def test_load_media_storage_config_defaults_to_filesystem_when_unset(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("MEDIA_STORAGE_BUCKET", raising=False)

    settings_module = importlib.import_module("config.settings")
    monkeypatch.setattr(settings_module, "BASE_DIR", tmp_path)

    assert settings_module.load_media_storage_config() == {
        "BACKEND": "django.core.files.storage.FileSystemStorage"
    }


def test_load_media_storage_config_returns_s3_backend_when_bucket_set(monkeypatch):
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


def test_load_media_storage_config_raises_when_bucket_set_but_secret_missing(
    monkeypatch,
):
    monkeypatch.setenv("MEDIA_STORAGE_BUCKET", "takulife-media")
    monkeypatch.setenv("MEDIA_STORAGE_ACCESS_KEY_ID", "key-id")
    # Empty string (not delenv) short-circuits _get_env's .env-file fallback,
    # matching the load_secret_key hard-fail test pattern above.
    monkeypatch.setenv("MEDIA_STORAGE_SECRET_ACCESS_KEY", "")
    monkeypatch.setenv(
        "MEDIA_STORAGE_ENDPOINT_URL", "https://example.r2.cloudflarestorage.com"
    )

    settings_module = importlib.import_module("config.settings")

    with pytest.raises(ImproperlyConfigured):
        settings_module.load_media_storage_config()


# ---------------------------------------------------------------------------
# PR-0d: proxy-aware client IP (TDD Coach checkpoints CP-1..CP-3)
# (.docs/plans/2026-07-14-stage0-deployment-foundation-plan.md §8 PR-0d)
# ---------------------------------------------------------------------------


def test_load_trusted_proxy_count_defaults_to_none_when_unset(monkeypatch, tmp_path):
    monkeypatch.delenv("TRUSTED_PROXY_COUNT", raising=False)

    settings_module = importlib.import_module("config.settings")
    monkeypatch.setattr(settings_module, "BASE_DIR", tmp_path)

    assert settings_module.load_trusted_proxy_count() is None


def test_load_trusted_proxy_count_parses_env_int(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_COUNT", "1")

    settings_module = importlib.import_module("config.settings")

    assert settings_module.load_trusted_proxy_count() == 1


def test_load_trusted_proxy_count_raises_for_non_integer_value(monkeypatch):
    monkeypatch.setenv("TRUSTED_PROXY_COUNT", "abc")

    settings_module = importlib.import_module("config.settings")

    with pytest.raises(ImproperlyConfigured):
        settings_module.load_trusted_proxy_count()


def test_build_axes_client_ip_callable_returns_none_when_trusted_proxy_count_falsy():
    settings_module = importlib.import_module("config.settings")

    assert settings_module.build_axes_client_ip_callable(None) is None
    assert settings_module.build_axes_client_ip_callable(0) is None


def test_build_axes_client_ip_callable_returns_core_ip_path_when_trusted_proxy_count_set():
    settings_module = importlib.import_module("config.settings")

    assert (
        settings_module.build_axes_client_ip_callable(1) == "core.ip.get_client_ip"
    )


def test_settings_module_wires_axes_client_ip_callable_attribute():
    settings_module = importlib.import_module("config.settings")

    assert settings_module.AXES_CLIENT_IP_CALLABLE == (
        settings_module.build_axes_client_ip_callable(
            settings_module.TRUSTED_PROXY_COUNT
        )
    )
