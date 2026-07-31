"""PersonalEntry API 테스트 — 사용자 소유의 비공개 비공식 아카이브 항목, 소유자
범위 한정. PersonalEntry는 공개 카탈로그에 절대 포함되지 않는다.

  POST   /api/personal-entries/        → 201 (소유자 = request.user)
  GET    /api/personal-entries/        → 페이지네이션 목록(사용자 범위 한정)
  GET    /api/personal-entries/<id>/   → 200 또는 404
  DELETE /api/personal-entries/<id>/   → 204 또는 404
"""
import uuid

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from archive.models import PersonalEntry


@pytest.mark.web
@pytest.mark.django_db
def test_개인_항목을_등록하면_요청자를_소유자로_저장하고_201을_응답한다(client, make_user):
    user = make_user(username="pe-create")

    client.force_login(user)
    response = client.post(
        "/api/personal-entries/",
        {"kind": "place", "title": "내가 발견한 장소", "memo": "즐겨찾음"},
        content_type="application/json",
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "내가 발견한 장소"
    assert data["kind"] == "place"
    entry = PersonalEntry.objects.get(id=data["id"])
    assert entry.user == user  # 소유자는 요청에서 가져오며 payload에서 가져오지 않는다


@pytest.mark.web
@pytest.mark.django_db
def test_개인_항목_목록_조회는_본인_소유로만_한정된다(client, make_user, make_entry):
    user = make_user(username="pe-scope")
    other = make_user(username="pe-scope-other")
    make_entry(user, kind="place", title="Mine")
    make_entry(other, kind="place", title="Theirs")

    client.force_login(user)
    response = client.get("/api/personal-entries/")

    assert response.status_code == 200
    titles = [row["title"] for row in response.json()["results"]]
    assert titles == ["Mine"]


@pytest.mark.web
@pytest.mark.django_db
def test_비로그인_사용자가_개인_항목_목록을_조회하면_인증_오류가_된다(client):
    response = client.get("/api/personal-entries/")
    assert response.status_code in (401, 403)


@pytest.mark.web
@pytest.mark.django_db
def test_개인_항목은_공개_행사_API_카탈로그에_노출되지_않는다(client, make_user, make_entry):
    """비공개 항목은 공개 Event 카탈로그 API에 노출되면 안 된다(SSR 쪽 테스트는
    tests/events/test_event_list_view.py로 분리됨)."""
    user = make_user(username="pe-leak")
    make_entry(user, kind="place", title="PRIVATE_LEAK_CANARY")

    client.force_login(user)
    api = client.get("/api/events/")

    assert api.status_code == 200
    assert "PRIVATE_LEAK_CANARY" not in api.content.decode()


@pytest.mark.web
@pytest.mark.django_db
def test_다른_사용자의_개인_항목을_삭제하면_404이고_삭제되지_않는다(client, make_user, make_entry):
    user = make_user(username="pe-del")
    other = make_user(username="pe-del-other")
    theirs = make_entry(other, kind="place", title="Theirs")

    client.force_login(user)
    response = client.delete(f"/api/personal-entries/{theirs.id}/")

    assert response.status_code == 404
    assert PersonalEntry.objects.filter(id=theirs.id).exists()


@pytest.mark.web
@pytest.mark.django_db
def test_본인_개인_항목의_장소명을_PATCH로_수정하면_200이고_DB에도_반영된다(client, make_user, make_entry):
    user = make_user(username="pe-patch-owner")
    entry = make_entry(user, kind="place", title="원래 제목", location_name="오타난 이름")

    client.force_login(user)
    response = client.patch(
        f"/api/personal-entries/{entry.id}/",
        {"location_name": "고친 이름"},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["location_name"] == "고친 이름"
    entry.refresh_from_db()
    assert entry.location_name == "고친 이름"
    assert entry.title == "원래 제목"  # 부분 수정 — 다른 필드는 그대로 남아야 한다


@pytest.mark.web
@pytest.mark.django_db
def test_개인_항목을_PATCH할_때_client_token을_같이_보내도_저장된_멱등_키는_바뀌지_않는다(
    client, make_user, make_entry
):
    """생성 시점의 멱등 키는 수정에서 다시 읽히거나 덮어써지면 안 된다(DAR 필수
    수정 ③), archive/serializers.py의 CollectionItemUpdateSerializer 기존
    가드와 동일하다."""
    user = make_user(username="pe-patch-token")
    original_token = uuid.UUID("11111111-1111-1111-1111-111111111111")
    replay_token = uuid.UUID("22222222-2222-2222-2222-222222222222")
    entry = make_entry(user, kind="place", title="원래 제목", client_token=original_token)

    client.force_login(user)
    response = client.patch(
        f"/api/personal-entries/{entry.id}/",
        {"location_name": "고친 이름", "client_token": str(replay_token)},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["location_name"] == "고친 이름"
    entry.refresh_from_db()
    assert entry.client_token == original_token


@pytest.mark.web
@pytest.mark.django_db
def test_굿즈_종류로_개인_항목을_등록하면_거부된다(client, make_user):
    """GOODS는 더 이상 PersonalEntry로 생성할 수 없다(컬렉션 도메인 설계안
    §3-3) — 굿즈는 전용 CollectionItem 도메인에 속한다."""
    user = make_user(username="pe-goods-blocked")

    client.force_login(user)
    response = client.post(
        "/api/personal-entries/",
        {"kind": "goods", "title": "차단되어야 할 굿즈"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not PersonalEntry.objects.filter(title="차단되어야 할 굿즈").exists()


@pytest.mark.domain
@pytest.mark.django_db
def test_개인_항목_시리얼라이저의_종류_선택지에_굿즈가_없다():
    """goods는 모델의 Kind enum에서 제거됐다(컬렉션 도메인 설계안 §3-5 M2) —
    시리얼라이저가 자동 생성하는 kind ChoiceField도 이를 반영해야 하며, 이미
    도달 불가능해진 validate_kind 가드만으로는 부족하다."""
    from archive.serializers import PersonalEntrySerializer

    assert "goods" not in dict(PersonalEntrySerializer().fields["kind"].choices)


# ---------------------------------------------------------------------------
# INTG-BE-01-PE-WEB (bfcache 중복 생성 방지 계획 §6) — PersonalEntry 생성 시
# client_token 멱등성의 HTTP 경계 계약. tests/archive/test_visit_records_api.py:153-192의
# INTG-BE-01-VR-WEB과 대응된다.
# ---------------------------------------------------------------------------


@pytest.mark.web
@pytest.mark.django_db
def test_같은_클라이언트_토큰으로_개인_항목_생성_POST를_두_번_보내면_두_응답_모두_201이고_동일한_id를_반환하며_DB에는_행이_하나만_생성된다(
    client, make_user
):
    user = make_user(username="pe-idempotent-token")
    client_token = str(uuid.uuid4())

    client.force_login(user)
    first_response = client.post(
        "/api/personal-entries/",
        {
            "kind": "place",
            "title": "첫 번째 제목",
            "client_token": client_token,
        },
        content_type="application/json",
    )
    second_response = client.post(
        "/api/personal-entries/",
        {
            "kind": "place",
            "title": "두 번째 제목",
            "client_token": client_token,
        },
        content_type="application/json",
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert first_response.json()["id"] == second_response.json()["id"]
    assert "client_token" not in first_response.json()
    assert "client_token" not in second_response.json()
    assert (
        PersonalEntry.objects.filter(user=user, client_token=client_token).count() == 1
    )
    entry = PersonalEntry.objects.get(user=user, client_token=client_token)
    assert entry.title == "첫 번째 제목"


# ---------------------------------------------------------------------------
# 이미지 업로드 — 방문 사진과 동일한 강화된 가드를 공유해야 한다
# ---------------------------------------------------------------------------


@pytest.mark.web
@pytest.mark.django_db
def test_이미지가_아닌_바이트를_이미지로_업로드하면_거부된다(client, make_user, settings, tmp_path):
    """.jpg로 위장한 가짜 바이트는 Pillow 내용 검사에서 거부되어야 한다."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user(username="pe-img-fake")

    client.force_login(user)
    response = client.post(
        "/api/personal-entries/",
        {
            "kind": "place",
            "title": "스푸핑 이미지",
            "image": SimpleUploadedFile(
                "not_an_image.jpg", b"notanimage", content_type="image/jpeg"
            ),
        },
    )

    assert response.status_code == 400
    assert "image" in response.json()
    assert not PersonalEntry.objects.filter(title="스푸핑 이미지").exists()


@pytest.mark.web
@pytest.mark.django_db
def test_5MB를_초과하는_이미지를_업로드하면_거부된다(client, make_user, png_bytes, settings, tmp_path):
    """5MB를 초과하는 이미지는 400으로 거부되어야 한다(압축 폭탄 방지 가드)."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user(username="pe-img-big")

    big_png = png_bytes()
    big_content = big_png + b"\x00" * (5 * 1024 * 1024 + 1 - len(big_png))

    client.force_login(user)
    response = client.post(
        "/api/personal-entries/",
        {
            "kind": "place",
            "title": "초대형 이미지",
            "image": SimpleUploadedFile("big.png", big_content, content_type="image/png"),
        },
    )

    assert response.status_code == 400
    assert "image" in response.json()


@pytest.mark.web
@pytest.mark.django_db
def test_SVG_파일을_이미지로_업로드하면_거부된다(client, make_user, settings, tmp_path):
    """SVG 파일은 Pillow가 허용하더라도 거부되어야 한다."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user(username="pe-img-svg")
    svg_content = b"<svg xmlns='http://www.w3.org/2000/svg'><circle r='5'/></svg>"

    client.force_login(user)
    response = client.post(
        "/api/personal-entries/",
        {
            "kind": "place",
            "title": "SVG 업로드",
            "image": SimpleUploadedFile("icon.svg", svg_content, content_type="image/svg+xml"),
        },
    )

    assert response.status_code == 400
    assert "image" in response.json()
