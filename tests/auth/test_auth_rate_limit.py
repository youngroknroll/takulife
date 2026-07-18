"""Rate-limit protection on authentication endpoints (allauth).

allauth ships ACCOUNT_RATE_LIMITS with sensible defaults already active; these
tests lock that behavior in so a future settings change cannot silently disable
brute-force / signup-flood protection. allauth's rate-limit counters live in
the shared DatabaseCache, and — like any cache write made inside a
``@pytest.mark.django_db`` test — are rolled back with that test's own
transaction (``clear_cache`` is no longer autouse; see tests/conftest.py's
``clear_cache`` docstring), so this file does not need to request it
explicitly.

Two distinct enforcement shapes are exercised, matching allauth's design:
- login_failed -> the login form refuses further authentication (even with the
  correct password) once the per-account window is exhausted (HTTP 200 + a
  localized non-field error, NOT a 429).
- signup / reset_password -> the view raises a 429 rendered via ``429.html``.
"""
import pytest
from django.test import override_settings

pytestmark = pytest.mark.slow


def _is_authenticated(client):
    """A protected page returns 200 when logged in, 302 (to login) otherwise."""
    return client.get("/archive/").status_code == 200


@pytest.mark.django_db
@override_settings(ACCOUNT_RATE_LIMITS={"login_failed": "2/m/key"})
def test_로그인_실패_횟수가_한도를_초과하면_올바른_비밀번호로도_로그인이_차단된다(
    client, make_verified_user, valid_password
):
    """After the per-account failure window is exhausted, the login form refuses
    to authenticate — even the correct password is rejected — which is what
    actually stops an online brute-force attack."""
    make_verified_user("victim@example.com")

    # Exhaust the 2/m/key window with wrong passwords.
    for _ in range(2):
        resp = client.post(
            "/accounts/login/",
            {"login": "victim@example.com", "password": "wrong-password"},
        )
        assert resp.status_code == 200, resp.status_code

    # The correct password is now refused: still on the form, not logged in.
    blocked = client.post(
        "/accounts/login/",
        {"login": "victim@example.com", "password": valid_password},
    )
    assert blocked.status_code == 200
    form = blocked.context["form"]
    assert form.non_field_errors(), "expected a throttle error on the login form"
    assert not _is_authenticated(client), "rate-limited login must not grant a session"


@pytest.mark.django_db
@override_settings(ACCOUNT_RATE_LIMITS={"signup": "2/m/ip"})
def test_회원가입_요청이_동일_ip에서_한도를_초과하면_429로_차단된다(client, valid_password):
    """Repeated signups from one IP are throttled with a 429 once exceeded."""
    for i in range(2):
        resp = client.post(
            "/accounts/signup/",
            {
                "email": f"newuser{i}@example.com",
                "password1": valid_password,
                "password2": valid_password,
                "terms_agreed": "on",
            },
        )
        assert resp.status_code in (200, 302), resp.status_code

    throttled = client.post(
        "/accounts/signup/",
        {
            "email": "newuser99@example.com",
            "password1": valid_password,
            "password2": valid_password,
            "terms_agreed": "on",
        },
    )
    assert throttled.status_code == 429, throttled.status_code


@pytest.mark.django_db
@override_settings(ACCOUNT_RATE_LIMITS={"reset_password": "2/m/ip"})
def test_비밀번호_재설정_요청이_동일_ip에서_한도를_초과하면_429로_차단된다(client, make_verified_user):
    """Repeated password-reset requests from one IP are throttled with a 429."""
    make_verified_user("reset@example.com")

    for _ in range(2):
        resp = client.post("/accounts/password/reset/", {"email": "reset@example.com"})
        assert resp.status_code in (200, 302), resp.status_code

    throttled = client.post(
        "/accounts/password/reset/", {"email": "reset@example.com"}
    )
    assert throttled.status_code == 429, throttled.status_code


@pytest.mark.django_db
@override_settings(ACCOUNT_RATE_LIMITS={"signup": "1/m/ip"})
def test_요청이_한도를_초과해_차단되면_한글_429_페이지가_렌더링된다(client, valid_password):
    """The 429 is served through the project's Korean ``429.html`` template,
    not allauth's bare English fallback."""
    client.post(
        "/accounts/signup/",
        {
            "email": "first@example.com",
            "password1": valid_password,
            "password2": valid_password,
            "terms_agreed": "on",
        },
    )
    throttled = client.post(
        "/accounts/signup/",
        {
            "email": "second@example.com",
            "password1": valid_password,
            "password2": valid_password,
            "terms_agreed": "on",
        },
    )
    assert throttled.status_code == 429
    assert "429.html" in [t.name for t in throttled.templates if t.name]
    body = throttled.content.decode("utf-8", "ignore")
    assert "요청이 너무 많습니다" in body


@pytest.mark.django_db
@override_settings(ACCOUNT_RATE_LIMITS={"login": "2/m/ip"})
def test_성공한_로그인도_login_한도에_포함되어_초과하면_429로_차단된다(
    client, make_verified_user, valid_password
):
    """allauth의 기본 ``login`` 한도(30/m/ip)는 config/settings.py가
    override하지 않아 병합으로 활성이며 성공 로그인까지 카운트한다 —
    tests/e2e/conftest.py의 autouse 캐시 격리 fixture가 보상하던 결함
    (TS-INF-04)을, 브라우저·live_server 없이 계층 하강해 방어한다.
    한도만 좁힐 뿐 운영 ACCOUNT_RATE_LIMITS는 무변경."""
    make_verified_user("loginlimit@example.com")

    for _ in range(2):
        client.logout()
        resp = client.post(
            "/accounts/login/",
            {"login": "loginlimit@example.com", "password": valid_password},
        )
        assert resp.status_code in (302, 200), resp.status_code

    client.logout()
    throttled = client.post(
        "/accounts/login/",
        {"login": "loginlimit@example.com", "password": valid_password},
    )
    assert throttled.status_code == 429, throttled.status_code
