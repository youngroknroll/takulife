"""닉네임 변경 페이지(/accounts/settings/nickname/, 트랙 29 NICK-15).
게이트·초기값 채움만 다룬다(선례 tests/auth/test_account_settings.py)."""
from django.core.cache import cache

import pytest

from accounts.forms import NicknameChangeForm
from accounts.validators import normalize_nickname

pytestmark = pytest.mark.web

NICKNAME_URL = "/accounts/settings/nickname/"


@pytest.mark.django_db
def test_로그인_사용자가_닉네임_변경_페이지에_접근하면_현재_닉네임이_채워진_폼이_렌더링된다(user_client):
    user, client = user_client(nickname="타쿠러")

    response = client.get(NICKNAME_URL)

    assert response.status_code == 200
    body = response.content.decode()
    assert 'name="nickname"' in body
    assert 'value="타쿠러"' in body


@pytest.mark.django_db
def test_비로그인_사용자는_닉네임_변경_페이지에서_로그인으로_리다이렉트된다(client):
    response = client.get(NICKNAME_URL)

    assert response.status_code == 302
    assert response["Location"].startswith("/accounts/login/")


@pytest.mark.django_db
def test_유효한_새_닉네임을_제출하면_닉네임이_갱신되고_같은_페이지로_리다이렉트된다(user_client):
    user, client = user_client(nickname="옛닉네임")

    response = client.post(NICKNAME_URL, {"nickname": "새이름"})

    assert response.status_code == 302
    assert response["Location"] == NICKNAME_URL
    user.refresh_from_db()
    assert user.nickname == "새이름"

    follow_up = client.get(NICKNAME_URL)
    assert "닉네임이 변경되었습니다." in follow_up.content.decode()


@pytest.mark.django_db
def test_타인이_사용중인_닉네임으로_변경을_시도하면_거부되고_기존_닉네임이_유지된다(user_client, make_user):
    make_user(nickname="Foo")
    user, client = user_client(nickname="원래닉")

    response = client.post(NICKNAME_URL, {"nickname": "foo"})

    assert response.status_code == 200
    assert "이미 사용 중인 닉네임입니다." in response.content.decode()
    user.refresh_from_db()
    assert user.nickname == "원래닉"


@pytest.mark.django_db
def test_자신의_현재_닉네임을_그대로_재제출하면_오류_없이_저장된다(user_client):
    user, client = user_client(nickname="그대로")

    response = client.post(NICKNAME_URL, {"nickname": "그대로"})

    assert response.status_code == 302


@pytest.mark.django_db
def test_한_시간_한도를_넘는_닉네임_변경은_DB_변경_없이_거부된다(user_client):
    cache.clear()
    user, client = user_client(nickname="원래")

    for i, value in enumerate(["첫번째", "두번째", "세번째", "네번째", "다섯번째"]):
        response = client.post(NICKNAME_URL, {"nickname": value})
        assert response.status_code == 302, (i, response.status_code)

    throttled = client.post(NICKNAME_URL, {"nickname": "여섯번째"})

    assert throttled.status_code == 200
    assert "닉네임 변경이 너무 잦습니다. 잠시 후 다시 시도해 주세요." in throttled.content.decode()
    user.refresh_from_db()
    assert user.nickname == "다섯번째"


@pytest.mark.django_db
def test_사전_중복_검사를_통과한_뒤_DB_제약에_걸리면_중복_오류로_안내된다(user_client, make_user, monkeypatch):
    # 폼의 iexact 사전 검사를 건너뛰어 두 요청이 거의 동시에 도착한
    # 경쟁 창을 재현한다 — 최후 방어는 DB UniqueConstraint다.
    monkeypatch.setattr(
        NicknameChangeForm,
        "clean_nickname",
        lambda self: normalize_nickname(self.cleaned_data["nickname"]),
    )
    make_user(nickname="Taku")
    user, client = user_client(nickname="원래닉")

    response = client.post(NICKNAME_URL, {"nickname": "taku"})

    assert response.status_code == 200
    body = response.content.decode()
    assert "이미 사용 중인 닉네임입니다." in body
    assert '<p class="account-menu-nickname">원래닉</p>' in body
    user.refresh_from_db()
    assert user.nickname == "원래닉"
