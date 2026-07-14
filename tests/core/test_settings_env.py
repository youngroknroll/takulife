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
