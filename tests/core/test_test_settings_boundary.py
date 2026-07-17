"""Test-infrastructure contracts (2026-07-17 test-suite speed track).

These guard the boundary introduced by `config/settings_test.py`: the
production settings module keeps its real password hasher, no production
entry point or deploy config ever loads the test-only settings module, and
the shared `make_user` fixture stops paying for a real password hash when a
test does not care about one.

See .docs/plans/2026-07-17-test-suite-improvement-plan.md §4 (TS-INF-01..03)
and .docs/plans/2026-07-17-test-code-execution-policy-design.md §5, §7.
"""
from pathlib import Path

import pytest
from django.conf import Settings


PROJECT_ROOT = Path(__file__).resolve().parents[2]

_PRODUCTION_SETTINGS_MODULE = "config.settings"

# Production code entry points must set DJANGO_SETTINGS_MODULE to the
# production module explicitly (not rely on some other default).
_ENTRY_POINTS_MUST_REFERENCE_PRODUCTION_SETTINGS = (
    "manage.py",
    "config/wsgi.py",
    "config/asgi.py",
)
_ENTRY_POINT_IDS = ("관리_명령", "WSGI_진입점", "ASGI_진입점")

# Entry points plus CI/deploy config: none of these may reference the
# test-only settings module. pytest's own config (pytest.ini) is the one
# legitimate place `settings_test` is referenced and is deliberately
# excluded from this list.
_DEPLOY_CONFIGS_MUST_NOT_REFERENCE_TEST_SETTINGS = (
    "manage.py",
    "config/wsgi.py",
    "config/asgi.py",
    ".github/workflows/ci.yml",
    "Dockerfile",
    "docker/entrypoint.sh",
    "docker-compose.yml",
)
_DEPLOY_CONFIG_IDS = (
    "관리_명령",
    "WSGI_진입점",
    "ASGI_진입점",
    "CI_워크플로",
    "Dockerfile",
    "도커_엔트리포인트",
    "도커_컴포즈",
)


@pytest.mark.contract
def test_운영_설정은_기본_강한_password_hasher_계약을_유지한다():
    # Given: 운영 설정 모듈(config.settings)을, 현재 활성 django.conf.settings
    # (테스트 실행 중에는 config.settings_test)와 독립적으로 로드한다.
    운영_설정 = Settings(_PRODUCTION_SETTINGS_MODULE)

    # When/Then: 첫 hasher가 PBKDF2이고 MD5 계열이 포함되지 않는다.
    assert 운영_설정.PASSWORD_HASHERS[0] == (
        "django.contrib.auth.hashers.PBKDF2PasswordHasher"
    )
    assert not any("MD5" in hasher for hasher in 운영_설정.PASSWORD_HASHERS)


@pytest.mark.contract
@pytest.mark.parametrize(
    "relative_path",
    _ENTRY_POINTS_MUST_REFERENCE_PRODUCTION_SETTINGS,
    ids=_ENTRY_POINT_IDS,
)
def test_운영_진입점은_운영_설정_모듈을_명시적으로_참조한다(relative_path):
    source = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")

    assert _PRODUCTION_SETTINGS_MODULE in source, relative_path


@pytest.mark.contract
@pytest.mark.parametrize(
    "relative_path",
    _DEPLOY_CONFIGS_MUST_NOT_REFERENCE_TEST_SETTINGS,
    ids=_DEPLOY_CONFIG_IDS,
)
def test_운영_진입점과_배포_설정은_테스트_전용_설정을_참조하지_않는다(relative_path):
    source = (PROJECT_ROOT / relative_path).read_text(encoding="utf-8")

    assert "settings_test" not in source, relative_path


@pytest.mark.domain
def test_비밀번호가_필요없는_사용자는_실해시를_만들지_않는다(make_user):
    # Given/When: 비밀번호를 지정하지 않고 사용자를 생성한다.
    비밀번호_미지정_사용자 = make_user()

    # Then: unusable password이므로 실제 password hasher 비용이 들지 않는다.
    assert 비밀번호_미지정_사용자.has_usable_password() is False
