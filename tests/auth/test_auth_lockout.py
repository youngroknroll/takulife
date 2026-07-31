"""로그인 엔드포인트의 django-axes 무차별 대입 잠금.

axes는 allauth의 창 단위 스로틀 위에 오래 지속되는 IP 잠금을 더한다. 이
테스트들은 allauth 자체의 login_failed 한도를 아주 높게 꺼 둬서 검증
대상이 오직 axes의 동작임을 분명히 한다.

axes는 시도 기록을 DB에 저장하며, 각 테스트의 ``@pytest.mark.django_db``
트랜잭션이 테스트마다 롤백한다 — 같은 롤백이 DatabaseCache 쓰기도 함께
되돌리므로(``clear_cache``는 더이상 autouse가 아니다, tests/conftest.py의
``clear_cache`` 독스트링 참고) 이 파일이 따로 요청할 필요가 없다.
``axes_reset``은 axes 자체 카운터를 깨끗한 상태로 보장한다.
"""
import pytest
from axes.utils import reset
from django.test import override_settings

pytestmark = pytest.mark.slow


@pytest.fixture
def axes_reset():
    reset()
    yield
    reset()


@pytest.mark.django_db
@override_settings(AXES_FAILURE_LIMIT=3, ACCOUNT_RATE_LIMITS={"login_failed": "1000/m/key"})
def test_로그인_3회_실패_후에는_올바른_비밀번호도_IP_단위로_잠긴다(
    client, axes_reset, make_verified_user, valid_password
):
    """AXES_FAILURE_LIMIT만큼 로그인이 실패하면 그 IP는 잠긴다 — 이후
    시도는 비밀번호가 맞아도 429로 막힌다."""
    make_verified_user("target@example.com")

    for _ in range(3):
        client.post(
            "/accounts/login/",
            {"login": "target@example.com", "password": "wrong-password"},
        )

    locked = client.post(
        "/accounts/login/",
        {"login": "target@example.com", "password": valid_password},
    )
    assert locked.status_code == 429, locked.status_code
    assert client.get("/archive/").status_code != 200, "locked-out login must not authenticate"


@pytest.mark.django_db
@override_settings(AXES_FAILURE_LIMIT=3, ACCOUNT_RATE_LIMITS={"login_failed": "1000/m/key"})
def test_IP_잠금_상태에서_로그인하면_한글_잠금_안내_템플릿이_렌더링된다(client, axes_reset, make_verified_user):
    """잠금 응답은 templates/account/lockout.html로 렌더된다."""
    make_verified_user("target2@example.com")

    for _ in range(3):
        client.post(
            "/accounts/login/",
            {"login": "target2@example.com", "password": "wrong-password"},
        )
    locked = client.post(
        "/accounts/login/",
        {"login": "target2@example.com", "password": "wrong-password"},
    )
    assert locked.status_code == 429
    body = locked.content.decode("utf-8", "ignore")
    assert "로그인 시도가 너무 많습니다" in body


@pytest.mark.django_db
@override_settings(
    AXES_FAILURE_LIMIT=3,
    ACCOUNT_RATE_LIMITS={"login_failed": "1000/m/key"},
    TRUSTED_PROXY_COUNT=1,
    AXES_CLIENT_IP_CALLABLE="core.ip.get_client_ip",
)
def test_신뢰된_프록시_뒤에서는_공유_프록시_주소가_아닌_전달된_클라이언트_IP_기준으로_잠긴다(
    client, axes_reset, make_verified_user, valid_password
):
    """QVL MEDIUM 후속: 신뢰된 프록시 뒤에서는 axes가 공유되는 프록시
    REMOTE_ADDR가 아니라 실제(X-Forwarded-For로 유도한) 클라이언트 IP를
    잠가야 한다 — 안 그러면 그 프록시 뒤의 공격자 한 명이 같은 프록시를
    쓰는 다른 사용자 전원을 잠가버린다."""
    make_verified_user("target3@example.com")

    for _ in range(3):
        client.post(
            "/accounts/login/",
            {"login": "target3@example.com", "password": "wrong-password"},
            REMOTE_ADDR="10.0.0.5",
            HTTP_X_FORWARDED_FOR="203.0.113.9",
        )

    attacker_retry = client.post(
        "/accounts/login/",
        {"login": "target3@example.com", "password": valid_password},
        REMOTE_ADDR="10.0.0.5",
        HTTP_X_FORWARDED_FOR="203.0.113.9",
    )
    assert attacker_retry.status_code == 429, attacker_retry.status_code

    other_client_attempt = client.post(
        "/accounts/login/",
        {"login": "target3@example.com", "password": valid_password},
        REMOTE_ADDR="10.0.0.5",
        HTTP_X_FORWARDED_FOR="198.51.100.5",
    )
    assert other_client_attempt.status_code != 429, other_client_attempt.status_code
