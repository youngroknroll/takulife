"""django-axes brute-force lockout on the login endpoint.

axes adds a durable IP lockout on top of allauth's per-window throttle. These
tests disable allauth's own login_failed limit (set very high) so the behavior
under test is unambiguously axes'.

axes stores attempts in the DB, rolled back per test by each test's own
``@pytest.mark.django_db`` transaction — the same rollback also undoes any
DatabaseCache writes (``clear_cache`` is no longer autouse; see
tests/conftest.py's ``clear_cache`` docstring), so this file does not need to
request it explicitly. ``axes_reset`` guarantees a clean slate for axes' own
counter.
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
    """After AXES_FAILURE_LIMIT failed logins the IP is locked out — a further
    attempt is blocked with 429 even when the password is correct."""
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
    """The lockout response is served via templates/account/lockout.html."""
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
    """PR-0d follow-up (QVL MEDIUM): behind a trusted proxy, axes must lock
    out the real (X-Forwarded-For-derived) client IP, not the shared proxy
    REMOTE_ADDR — otherwise one attacker behind the proxy locks out every
    other user sharing that proxy."""
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
