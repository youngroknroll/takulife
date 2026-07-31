"""테스트 인프라 계약(테스트 스위트 속도 개선 트랙).

`config/settings_test.py`가 도입한 경계를 지킨다: 프로덕션 설정 모듈은
실제 비밀번호 해셔를 그대로 유지하고, 어떤 프로덕션 진입점이나 배포
설정도 테스트 전용 설정 모듈을 로드하지 않으며, 공용 `make_user` 픽스처는
테스트가 비밀번호 해시를 신경 쓰지 않을 때 그 비용을 치르지 않는다.

.docs/plans/2026-07-17-test-suite-improvement-plan.md §4(TS-INF-01..03)와
.docs/plans/2026-07-17-test-code-execution-policy-design.md §5, §7 참고.
"""
from pathlib import Path

import pytest
from django.conf import Settings


PROJECT_ROOT = Path(__file__).resolve().parents[2]

_PRODUCTION_SETTINGS_MODULE = "config.settings"

# 프로덕션 코드 진입점은 DJANGO_SETTINGS_MODULE을 다른 기본값에 기대지
# 않고 프로덕션 모듈로 명시적으로 설정해야 한다.
_ENTRY_POINTS_MUST_REFERENCE_PRODUCTION_SETTINGS = (
    "manage.py",
    "config/wsgi.py",
    "config/asgi.py",
)
_ENTRY_POINT_IDS = ("관리_명령", "WSGI_진입점", "ASGI_진입점")

# 진입점과 CI/배포 설정: 이 중 어느 것도 테스트 전용 설정 모듈을 참조하면
# 안 된다. `settings_test`를 참조해도 되는 유일한 정당한 곳은 pytest
# 자체 설정(pytest.ini)이라 이 목록에서 일부러 뺐다.
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
