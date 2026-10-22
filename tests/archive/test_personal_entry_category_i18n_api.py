"""트랙 43-3: 개인 항목 분류는 어느 언어로 보내도 한국어 원문으로 저장된다.

영어 UI의 제안 칩("Pop-up store")이 그대로 저장되면 언어에 따라 데이터가
갈라지므로(docs/BE/i18n.md 가드레일 20) 생성·수정 모두 시리얼라이저가
한국어 원문으로 되돌린다.
"""
import uuid

import pytest

from archive.models import PersonalEntry

pytestmark = [pytest.mark.web, pytest.mark.django_db]

_EN = {"HTTP_ACCEPT_LANGUAGE": "en"}
_JA = {"HTTP_ACCEPT_LANGUAGE": "ja"}


def _create(client, category, **headers):
    return client.post(
        "/api/personal-entries/",
        {"kind": "place", "title": "내 장소", "category": category},
        content_type="application/json",
        **headers,
    )


def test_영어_요청으로_Pop_up_store를_등록하면_한국어_원문으로_응답하고_저장한다(client, make_user):
    client.force_login(make_user(username="pec-en-create"))

    response = _create(client, "Pop-up store", **_EN)

    assert response.status_code == 201
    assert response.json()["category"] == "팝업스토어"
    assert PersonalEntry.objects.get(id=response.json()["id"]).category == "팝업스토어"


def test_일본어_요청으로_영어_칩_Exhibition을_등록해도_전시로_저장한다(client, make_user):
    client.force_login(make_user(username="pec-ja-create"))

    response = _create(client, "Exhibition", **_JA)

    assert response.status_code == 201
    assert PersonalEntry.objects.get(id=response.json()["id"]).category == "전시"


def test_한국어_요청으로_영어_칩_Exhibition을_등록해도_전시로_저장한다(client, make_user):
    client.force_login(make_user(username="pec-ko-create"))

    response = _create(client, "Exhibition")

    assert response.status_code == 201
    assert PersonalEntry.objects.get(id=response.json()["id"]).category == "전시"


def test_일본어_칩_문구를_영어_요청으로_보내도_한국어_원문으로_저장한다(client, make_user):
    client.force_login(make_user(username="pec-cross-lang"))

    response = _create(client, "聖地巡礼", **_EN)

    assert response.status_code == 201
    assert PersonalEntry.objects.get(id=response.json()["id"]).category == "성지순례"


def test_분류_자유_입력은_변환하지_않고_그대로_저장한다(client, make_user):
    client.force_login(make_user(username="pec-free"))

    response = _create(client, "내 분류", **_EN)

    assert response.status_code == 201
    assert response.json()["category"] == "내 분류"
    assert PersonalEntry.objects.get(id=response.json()["id"]).category == "내 분류"


def test_한국어_원문_분류는_영어_요청에서도_그대로_저장한다(client, make_user):
    client.force_login(make_user(username="pec-source"))

    response = _create(client, "카페", **_EN)

    assert response.status_code == 201
    assert PersonalEntry.objects.get(id=response.json()["id"]).category == "카페"


def test_수정_요청에서도_영어_칩을_보내면_한국어_원문으로_저장한다(client, make_user, make_entry):
    user = make_user(username="pec-patch")
    entry = make_entry(user, kind="place", title="원래 제목", category="기타")

    client.force_login(user)
    response = client.patch(
        f"/api/personal-entries/{entry.id}/",
        {"category": "Goods shop"},
        content_type="application/json",
        **_EN,
    )

    assert response.status_code == 200
    assert response.json()["category"] == "굿즈숍"
    entry.refresh_from_db()
    assert entry.category == "굿즈숍"


def test_수정_요청의_분류_자유_입력은_그대로_저장한다(client, make_user, make_entry):
    user = make_user(username="pec-patch-free")
    entry = make_entry(user, kind="place", title="원래 제목", category="카페")

    client.force_login(user)
    response = client.patch(
        f"/api/personal-entries/{entry.id}/",
        {"category": "내 분류"},
        content_type="application/json",
        **_EN,
    )

    assert response.status_code == 200
    entry.refresh_from_db()
    assert entry.category == "내 분류"


def test_같은_토큰으로_영어_칩을_다시_보내도_행은_하나이고_분류는_원문이다(client, make_user):
    user = make_user(username="pec-idempotent")
    token = str(uuid.uuid4())
    payload = {"kind": "place", "title": "내 장소", "category": "Pop-up store", "client_token": token}

    client.force_login(user)
    first = client.post("/api/personal-entries/", payload, content_type="application/json", **_EN)
    second = client.post("/api/personal-entries/", payload, content_type="application/json", **_EN)

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["category"] == "팝업스토어"
    assert PersonalEntry.objects.filter(user=user, client_token=token).count() == 1
    assert PersonalEntry.objects.get(user=user, client_token=token).category == "팝업스토어"
