"""django-axes brute-force lockout on the login endpoint.

axes adds a durable IP lockout on top of allauth's per-window throttle. These
tests disable allauth's own login_failed limit (set very high) so the behavior
under test is unambiguously axes'.

The autouse ``clear_cache`` fixture handles the cache; axes stores attempts in
the DB (rolled back per test), and ``axes_reset`` guarantees a clean slate.
"""
import pytest
from axes.utils import reset
from django.test import override_settings


@pytest.fixture
def axes_reset():
    reset()
    yield
    reset()


@pytest.mark.django_db
@override_settings(AXES_FAILURE_LIMIT=3, ACCOUNT_RATE_LIMITS={"login_failed": "1000/m/key"})
def test_axes_locks_out_ip_after_repeated_failed_logins(
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
def test_axes_lockout_renders_korean_template(client, axes_reset, make_verified_user):
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
def test_axes_lockout_keys_by_forwarded_ip_behind_trusted_proxy(
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
