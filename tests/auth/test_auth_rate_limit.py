"""인증 엔드포인트의 요청 한도 보호(allauth).

allauth는 이미 합리적인 기본값으로 ACCOUNT_RATE_LIMITS를 켠 채로 나온다.
이 테스트들은 그 동작을 고정해, 나중에 설정이 바뀌어도 무차별 대입/가입
폭주 방어가 조용히 꺼지지 않게 한다. allauth의 요청 한도 카운터는 공유
DatabaseCache에 있고, ``@pytest.mark.django_db`` 테스트 안의 다른 캐시
쓰기와 마찬가지로 그 테스트의 트랜잭션과 함께 롤백된다(``clear_cache``는
더이상 autouse가 아니다, tests/conftest.py의 ``clear_cache`` 독스트링
참고) — 그래서 이 파일이 따로 요청할 필요가 없다.

allauth의 설계를 따라 서로 다른 두 가지 강제 방식을 검증한다:
- login_failed -> 계정별 창이 소진되면 로그인 폼이 (맞는 비밀번호로도)
  더이상 인증을 허용하지 않는다(HTTP 200 + 지역화된 필드 무관 오류, 429가
  아니다).
- signup / reset_password -> 뷰가 ``429.html``로 렌더되는 429를 던진다.
"""
import pytest
from django.test import override_settings

pytestmark = pytest.mark.slow


def _is_authenticated(client):
    """보호된 페이지는 로그인 상태면 200, 아니면 (로그인으로) 302를
    돌려준다."""
    return client.get("/archive/").status_code == 200


@pytest.mark.django_db
@override_settings(ACCOUNT_RATE_LIMITS={"login_failed": "2/m/key"})
def test_로그인_실패_횟수가_한도를_초과하면_올바른_비밀번호로도_로그인이_차단된다(
    client, make_verified_user, valid_password
):
    """계정별 실패 창이 소진되면 로그인 폼은 (맞는 비밀번호여도) 더이상
    인증을 허용하지 않는다 — 이게 실제로 온라인 무차별 대입 공격을
    막는다."""
    make_verified_user("victim@example.com")

    # 틀린 비밀번호로 2/m/key 창을 소진한다.
    for _ in range(2):
        resp = client.post(
            "/accounts/login/",
            {"login": "victim@example.com", "password": "wrong-password"},
        )
        assert resp.status_code == 200, resp.status_code

    # 이제 맞는 비밀번호도 거부된다: 여전히 폼에 머물고 로그인되지 않는다.
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
    """같은 IP에서 반복되는 가입은 한도를 넘으면 429로 스로틀된다."""
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
@override_settings(ACCOUNT_RATE_LIMITS={"signup": "2/m/ip"})
def test_소셜_가입_요청이_동일_ip에서_한도를_초과하면_429로_차단된다(client):
    """소셜 가입도 signup 창을 공유한다. allauth는 GET을 한도 계산에서
    제외하므로(allauth core/internal/ratelimit.py:186의 limit_get) POST로
    소비를 재현한다 — 폼 유효성과 무관하게 한도 판정은 dispatch 진입 전에
    끝나므로 본문은 빈 값이어도 된다."""
    for _ in range(2):
        resp = client.post("/accounts/3rdparty/signup/", {})
        assert resp.status_code != 429, resp.status_code

    throttled = client.post("/accounts/3rdparty/signup/", {})
    assert throttled.status_code == 429, throttled.status_code


@pytest.mark.django_db
@override_settings(ACCOUNT_RATE_LIMITS={"reset_password": "2/m/ip"})
def test_비밀번호_재설정_요청이_동일_ip에서_한도를_초과하면_429로_차단된다(client, make_verified_user):
    """같은 IP에서 반복되는 비밀번호 재설정 요청은 429로 스로틀된다."""
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
    """429는 allauth의 밋밋한 영어 폴백이 아니라 프로젝트의 한글
    ``429.html`` 템플릿으로 렌더된다."""
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
