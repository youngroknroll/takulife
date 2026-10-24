"""트랙 43-3: 굿즈 유형은 어느 언어로 보내도 한국어 원문으로 저장된다.

영어 UI의 유형 칩("Keychain")이 `item_type`에 그대로 저장되면 정확 일치
필터(archive/queries.py)에서 "키링"과 갈라진다. 생성·수정 시리얼라이저가
한국어 원문으로 되돌린다.
"""
import pytest

from archive.models import CollectionItem

pytestmark = [pytest.mark.web, pytest.mark.django_db]

_EN = {"HTTP_ACCEPT_LANGUAGE": "en"}
_JA = {"HTTP_ACCEPT_LANGUAGE": "ja"}


def _create(client, item_type, name="새 굿즈", **headers):
    return client.post(
        "/api/collection-items/",
        {"name": name, "item_type": item_type},
        content_type="application/json",
        **headers,
    )


def test_영어_요청으로_Keychain을_등록하면_키링으로_응답하고_저장한다(client, make_user):
    client.force_login(make_user(username="cit-en-create"))

    response = _create(client, "Keychain", **_EN)

    assert response.status_code == 201
    assert response.json()["item_type"] == "키링"
    assert CollectionItem.objects.get(id=response.json()["id"]).item_type == "키링"


def test_일본어_칩_문구를_영어_요청으로_보내도_한국어_원문으로_저장한다(client, make_user):
    client.force_login(make_user(username="cit-cross-lang"))

    response = _create(client, "キーホルダー", **_EN)

    assert response.status_code == 201
    assert CollectionItem.objects.get(id=response.json()["id"]).item_type == "키링"


def test_한국어_요청으로_영어_유형을_보내도_한국어_원문으로_저장한다(client, make_user):
    client.force_login(make_user(username="cit-ko-create"))

    response = _create(client, "Photocard")

    assert response.status_code == 201
    assert CollectionItem.objects.get(id=response.json()["id"]).item_type == "포토카드"


def test_굿즈_유형_자유_입력은_변환하지_않고_그대로_저장한다(client, make_user):
    client.force_login(make_user(username="cit-free"))

    response = _create(client, "내 유형", **_EN)

    assert response.status_code == 201
    assert CollectionItem.objects.get(id=response.json()["id"]).item_type == "내 유형"


def test_한국어_원문_굿즈_유형은_영어_요청에서도_그대로_저장한다(client, make_user):
    client.force_login(make_user(username="cit-source"))

    response = _create(client, "뱃지", **_JA)

    assert response.status_code == 201
    assert CollectionItem.objects.get(id=response.json()["id"]).item_type == "뱃지"


def test_수정_요청에서도_영어_유형을_보내면_한국어_원문으로_저장한다(client, make_user, make_collection_item):
    user = make_user(username="cit-patch")
    item = make_collection_item(user, name="원래 이름", item_type="뱃지")

    client.force_login(user)
    response = client.patch(
        f"/api/collection-items/{item.id}/",
        {"item_type": "Plush"},
        content_type="application/json",
        **_EN,
    )

    assert response.status_code == 200
    assert response.json()["item_type"] == "인형"
    item.refresh_from_db()
    assert item.item_type == "인형"


def test_영어로_등록한_굿즈는_한국어_원문_필터로_조회된다(client, make_user, make_collection_item):
    user = make_user(username="cit-filter")
    make_collection_item(user, name="다른 굿즈", item_type="뱃지")
    client.force_login(user)
    created = _create(client, "Keychain", name="영어로 등록", **_EN)
    assert created.status_code == 201

    response = client.get("/api/collection-items/?item_type=키링")

    assert response.status_code == 200
    assert [row["name"] for row in response.json()["results"]] == ["영어로 등록"]
