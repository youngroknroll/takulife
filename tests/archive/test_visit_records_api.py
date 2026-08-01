"""
archive 앱의 방문 기록 API 테스트 모음.

경로는 모두 /api/visit-records/ 와 /api/visit-records/<pk>/photos/ 아래에 있다.
사진 업로드 보안: 실제 Pillow 기반 ImageField 검증, 확장자 허용목록
(jpg/jpeg/png/webp만), 5MB 상한, 압축폭탄 가드, 기록당 사진 5장 상한.
"""

import io
import uuid

import PIL.Image
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from archive.models import UserEventStatus, VisitRecord, VisitRecordPhoto
from archive.services import MAX_PHOTOS_PER_RECORD

pytestmark = pytest.mark.web


# ---------------------------------------------------------------------------
# VisitRecord 생성 (POST /api/visit-records/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_로그인한_사용자가_방문_기록을_생성하면_저장된_방문_기록이_응답에_반영된다(client, make_user, make_event):
    user = make_user()
    event = make_event()

    client.force_login(user)
    response = client.post(
        "/api/visit-records/",
        {"event": event.id, "visited_on": "2026-05-26", "short_review": "great"},
        content_type="application/json",
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["event"] == event.id
    assert payload["visited_on"] == "2026-05-26"
    assert payload["short_review"] == "great"
    assert VisitRecord.objects.filter(user=user, event=event).exists()


@pytest.mark.django_db
def test_방문_기록을_생성하면_요청한_사용자_소유로만_저장된다(client, make_user, make_event):
    user = make_user()
    other_user = make_user()
    event = make_event()

    client.force_login(user)
    client.post(
        "/api/visit-records/",
        {"event": event.id, "visited_on": "2026-05-26"},
        content_type="application/json",
    )

    assert VisitRecord.objects.filter(user=user, event=event).count() == 1
    assert VisitRecord.objects.filter(user=other_user, event=event).count() == 0


@pytest.mark.django_db
def test_미게시_행사를_대상으로_방문_기록을_생성하면_요청이_거부된다(client, make_user, make_draft_event):
    user = make_user()
    draft_event = make_draft_event()

    client.force_login(user)
    response = client.post(
        "/api/visit-records/",
        {"event": draft_event.id, "visited_on": "2026-05-26"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert VisitRecord.objects.count() == 0


@pytest.mark.django_db
def test_비로그인_사용자가_방문_기록_생성을_요청하면_거부된다(client, make_event):
    event = make_event()

    response = client.post(
        "/api/visit-records/",
        {"event": event.id, "visited_on": "2026-05-26"},
        content_type="application/json",
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# 생성 시 상태 대상이 visited로 자동 전환된다 (PR-C3 오케스트레이션)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_참석_예정_행사에_방문_기록을_생성하면_상태가_방문_완료로_자동_전환된다(
    client, make_user, make_event, make_status
):
    user = make_user()
    event = make_event()
    make_status(user, event, status=UserEventStatus.Status.PLANNED)

    client.force_login(user)
    response = client.post(
        "/api/visit-records/",
        {"event": event.id, "visited_on": "2026-05-26"},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert UserEventStatus.objects.get(user=user, event=event).status == (
        UserEventStatus.Status.VISITED
    )


# ---------------------------------------------------------------------------
# 한 행사에 여러 방문 기록이 허용된다 (unique 제약 없음)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_같은_행사에_방문_기록을_여러_번_생성하면_모두_저장된다(client, make_user, make_event):
    user = make_user()
    event = make_event()

    client.force_login(user)
    r1 = client.post(
        "/api/visit-records/",
        {"event": event.id, "visited_on": "2026-05-26"},
        content_type="application/json",
    )
    r2 = client.post(
        "/api/visit-records/",
        {"event": event.id, "visited_on": "2026-05-27"},
        content_type="application/json",
    )

    assert r1.status_code == 201
    assert r2.status_code == 201
    assert VisitRecord.objects.filter(user=user, event=event).count() == 2


# ---------------------------------------------------------------------------
# INTG-BE-01-VR-WEB (bfcache 중복 생성 계획 §6) — VisitRecord 생성의
# client_token 멱등성에 대한 HTTP 경계 계약. tests/archive/test_collection_items_api.py의
# INTG-BE-01-CI-WEB와 대응한다.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_같은_클라이언트_토큰으로_방문_기록_생성_POST를_두_번_보내면_두_응답_모두_201이고_동일한_id를_반환하며_DB에는_행이_하나만_생성된다(
    client, make_user, make_event
):
    user = make_user()
    event = make_event()
    client_token = str(uuid.uuid4())

    client.force_login(user)
    first_response = client.post(
        "/api/visit-records/",
        {
            "event": event.id,
            "visited_on": "2026-05-26",
            "short_review": "first",
            "client_token": client_token,
        },
        content_type="application/json",
    )
    second_response = client.post(
        "/api/visit-records/",
        {
            "event": event.id,
            "visited_on": "2026-05-26",
            "short_review": "second",
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
        VisitRecord.objects.filter(user=user, client_token=client_token).count() == 1
    )
    record = VisitRecord.objects.get(user=user, client_token=client_token)
    assert record.short_review == "first"


# ---------------------------------------------------------------------------
# INTG-BE-05-VR (bfcache 중복 생성 계획 §6, 검증 경계 "web/slow") —
# tests/archive/test_collection_items_api.py의 INTG-BE-05-CI와 대응: 생성
# 엔드포인트는 위의 client_token 멱등성 가드와 별개로 반복 POST 폭주를
# 분당 30회 스로틀로 막아야 한다. 같은 행사를 30번 재사용해(위에서 증명했듯
# 한 행사에 여러 방문 허용) 31번째 요청을 막는 것이 비즈니스 규칙 거부가
# 아니라 스로틀임을 보인다. GET(목록)은 영향받지 않아야 한다.
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.django_db
def test_방문_기록_생성_요청이_설정된_한도를_초과하면_429로_제한된다(client, make_user, make_event):
    user = make_user()
    event = make_event()
    client.force_login(user)

    # 분당 30회 한도: 30번은 성공하고 31번째는 스로틀된다.
    for i in range(30):
        response = client.post(
            "/api/visit-records/",
            {"event": event.id, "visited_on": "2026-05-26"},
            content_type="application/json",
        )
        assert response.status_code == 201, f"create {i} should succeed"

    throttled = client.post(
        "/api/visit-records/",
        {"event": event.id, "visited_on": "2026-05-26"},
        content_type="application/json",
    )

    assert throttled.status_code == 429
    assert VisitRecord.objects.count() == 30

    listed = client.get("/api/visit-records/")
    assert listed.status_code == 200


# ---------------------------------------------------------------------------
# VisitRecord 목록 (GET /api/visit-records/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_방문_기록_목록을_조회하면_본인_기록만_반환된다(client, make_user, make_event, make_visit):
    user = make_user()
    other_user = make_user()
    event = make_event()
    owned = make_visit(user, event=event, visited_on="2026-05-26")
    make_visit(other_user, event=event, visited_on="2026-05-27")

    client.force_login(user)
    response = client.get("/api/visit-records/")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"count", "next", "previous", "results"}
    assert payload["count"] == 1
    assert payload["results"][0]["id"] == owned.id


@pytest.mark.django_db
def test_방문_기록이_페이지_크기를_초과하면_목록이_페이지네이션된다(client, make_user, make_event, make_visit):
    user = make_user()
    event = make_event()
    for i in range(21):
        make_visit(user, event=event, visited_on=f"2026-05-{str(i + 1).zfill(2)}")

    client.force_login(user)
    response = client.get("/api/visit-records/")

    assert response.status_code == 200
    payload = response.json()
    assert payload["count"] == 21
    assert len(payload["results"]) == 20
    assert payload["next"] is not None


# ---------------------------------------------------------------------------
# VisitRecord 상세 (GET /api/visit-records/<pk>/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_본인_방문_기록을_상세_조회하면_해당_기록이_반환된다(client, make_user, make_event, make_visit):
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")

    client.force_login(user)
    response = client.get(f"/api/visit-records/{record.id}/")

    assert response.status_code == 200
    assert response.json()["id"] == record.id


@pytest.mark.django_db
def test_타인의_방문_기록을_상세_조회하면_404가_반환된다(client, make_user, make_event, make_visit):
    owner = make_user()
    attacker = make_user()
    event = make_event()
    record = make_visit(owner, event=event, visited_on="2026-05-26")

    client.force_login(attacker)
    response = client.get(f"/api/visit-records/{record.id}/")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# VisitRecord 삭제 (DELETE /api/visit-records/<pk>/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_본인_방문_기록을_삭제하면_기록이_제거된다(client, make_user, make_event, make_visit):
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")

    client.force_login(user)
    response = client.delete(f"/api/visit-records/{record.id}/")

    assert response.status_code == 204
    assert not VisitRecord.objects.filter(pk=record.id).exists()


@pytest.mark.django_db
def test_타인의_방문_기록_삭제를_시도하면_404가_반환되고_기록이_유지된다(client, make_user, make_event, make_visit):
    owner = make_user()
    attacker = make_user()
    event = make_event()
    record = make_visit(owner, event=event, visited_on="2026-05-26")

    client.force_login(attacker)
    response = client.delete(f"/api/visit-records/{record.id}/")

    assert response.status_code == 404
    assert VisitRecord.objects.filter(pk=record.id).exists()


# ---------------------------------------------------------------------------
# VisitRecord 수정 (PATCH /api/visit-records/<pk>/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_본인_방문_기록을_수정하면_변경한_필드가_저장된다(client, make_user, make_event, make_visit):
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26", short_review="old")

    client.force_login(user)
    response = client.patch(
        f"/api/visit-records/{record.id}/",
        {"visited_on": "2026-06-01", "short_review": "updated"},
        content_type="application/json",
    )

    assert response.status_code == 200
    record.refresh_from_db()
    assert str(record.visited_on) == "2026-06-01"
    assert record.short_review == "updated"


@pytest.mark.django_db
def test_방문_기록_수정_요청에_대상_변경을_포함해도_대상은_그대로_유지된다(client, make_user, make_event, make_visit):
    user = make_user()
    event = make_event()
    other_event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")

    client.force_login(user)
    response = client.patch(
        f"/api/visit-records/{record.id}/",
        {"event": other_event.id, "short_review": "memo"},
        content_type="application/json",
    )

    assert response.status_code == 200
    record.refresh_from_db()
    # 대상은 원래 event로 고정되고 short_review만 바뀐다.
    assert record.event_id == event.id
    assert record.short_review == "memo"


@pytest.mark.django_db
def test_타인의_방문_기록_수정을_시도하면_404가_반환되고_내용이_유지된다(client, make_user, make_event, make_visit):
    owner = make_user()
    attacker = make_user()
    event = make_event()
    record = make_visit(owner, event=event, visited_on="2026-05-26", short_review="old")

    client.force_login(attacker)
    response = client.patch(
        f"/api/visit-records/{record.id}/",
        {"short_review": "hacked"},
        content_type="application/json",
    )

    assert response.status_code == 404
    record.refresh_from_db()
    assert record.short_review == "old"


@pytest.mark.django_db
def test_비로그인_사용자가_방문_기록_수정을_요청하면_거부된다(client, make_user, make_event, make_visit):
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")

    response = client.patch(
        f"/api/visit-records/{record.id}/",
        {"short_review": "x"},
        content_type="application/json",
    )

    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# 사진 업로드 (POST /api/visit-records/<record_id>/photos/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_본인_방문_기록에_사진을_업로드하면_사진이_저장된다(client, make_user, make_event, png_bytes, settings, tmp_path, make_visit):
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")

    client.force_login(user)
    response = client.post(
        f"/api/visit-records/{record.id}/photos/",
        {"image": SimpleUploadedFile("photo.png", png_bytes(), content_type="image/png")},
    )

    assert response.status_code == 201
    assert VisitRecordPhoto.objects.filter(visit_record=record).count() == 1


@pytest.mark.django_db
def test_타인의_방문_기록에_사진_업로드를_시도하면_404가_반환된다(client, make_user, make_event, png_bytes, settings, tmp_path, make_visit):
    settings.MEDIA_ROOT = str(tmp_path)
    owner = make_user()
    attacker = make_user()
    event = make_event()
    record = make_visit(owner, event=event, visited_on="2026-05-26")

    client.force_login(attacker)
    response = client.post(
        f"/api/visit-records/{record.id}/photos/",
        {"image": SimpleUploadedFile("photo.png", png_bytes(), content_type="image/png")},
    )

    assert response.status_code == 404
    assert VisitRecordPhoto.objects.count() == 0


@pytest.mark.django_db
def test_이미지_없이_사진_업로드를_요청하면_400이_반환된다(client, make_user, make_event, settings, tmp_path, make_visit):
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")

    client.force_login(user)
    response = client.post(
        f"/api/visit-records/{record.id}/photos/",
        {},
    )

    assert response.status_code == 400
    assert "image" in response.json()


@pytest.mark.django_db
def test_이미지가_아닌_바이트를_사진으로_업로드하면_거부된다(client, make_user, make_event, settings, tmp_path, make_visit):
    """.jpg로 위장한 가짜 바이트는 Pillow 내용 검사로 거부되어야 한다."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")

    client.force_login(user)
    response = client.post(
        f"/api/visit-records/{record.id}/photos/",
        {"image": SimpleUploadedFile("not_an_image.jpg", b"notanimage", content_type="image/jpeg")},
    )

    assert response.status_code == 400
    assert "image" in response.json()


@pytest.mark.django_db
def test_5MB를_초과하는_사진을_업로드하면_거부된다(client, make_user, make_event, png_bytes, settings, tmp_path, make_visit):
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")

    big_png = png_bytes()
    big_content = big_png + b"\x00" * (5 * 1024 * 1024 + 1 - len(big_png))

    client.force_login(user)
    response = client.post(
        f"/api/visit-records/{record.id}/photos/",
        {"image": SimpleUploadedFile("big.png", big_content, content_type="image/png")},
    )

    assert response.status_code == 400
    assert "image" in response.json()


@pytest.mark.django_db
def test_허용되지_않는_확장자인_SVG_파일을_업로드하면_거부된다(client, make_user, make_event, settings, tmp_path, make_visit):
    """SVG는 Pillow가 허용할 수 있더라도 거부되어야 한다."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")
    svg_content = b"<svg xmlns='http://www.w3.org/2000/svg'><circle r='5'/></svg>"

    client.force_login(user)
    response = client.post(
        f"/api/visit-records/{record.id}/photos/",
        {"image": SimpleUploadedFile("icon.svg", svg_content, content_type="image/svg+xml")},
    )

    assert response.status_code == 400
    assert "image" in response.json()


@pytest.mark.django_db
def test_PNG로_위장한_BMP_파일을_업로드하면_실제_포맷_기준으로_거부된다(client, make_user, make_event, settings, tmp_path, make_visit):
    """.png로 확장자만 바꾼 정상 BMP 파일은 거부되어야 한다.

    확장자 허용목록만으로는 공격자가 조작할 수 있으므로, Pillow가 실제로
    디코딩한 포맷을 기준으로 판단해야 한다 (S1).
    """
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")

    buf = io.BytesIO()
    PIL.Image.new("RGB", (10, 10), color=(0, 255, 0)).save(buf, format="BMP")
    spoofed = SimpleUploadedFile("photo.png", buf.getvalue(), content_type="image/png")

    client.force_login(user)
    response = client.post(
        f"/api/visit-records/{record.id}/photos/",
        {"image": spoofed},
    )

    assert response.status_code == 400
    assert "image" in response.json()
    assert VisitRecordPhoto.objects.filter(visit_record=record).count() == 0


@pytest.mark.django_db
def test_픽셀_면적_상한을_초과하는_이미지를_업로드하면_거부된다(client, make_user, make_event, png_bytes, settings, tmp_path, monkeypatch, make_visit):
    """축별 상한 안에 있어도 전체 픽셀 면적 상한을 넘으면 거부되어야 한다.

    면적 가드가 5MB 바이트 상한, 축별 크기 상한과 독립적임을 증명한다
    (S2). CI에서 실제 압축폭탄을 만들지 않도록 상한을 작게 monkeypatch한다.
    """
    settings.MEDIA_ROOT = str(tmp_path)
    monkeypatch.setattr("events.image_validation.MAX_IMAGE_PIXELS_LIMIT", 50)
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")

    # 10x10=100px는 상한 50을 넘지만, 각 축(10)은 MAX_IMAGE_DIMENSION_PX보다
    # 훨씬 작고 바이트 크기도 수백 바이트에 불과하다.
    png_data = png_bytes(10, 10)

    client.force_login(user)
    response = client.post(
        f"/api/visit-records/{record.id}/photos/",
        {"image": SimpleUploadedFile("photo.png", png_data, content_type="image/png")},
    )

    assert response.status_code == 400
    assert "image" in response.json()
    assert VisitRecordPhoto.objects.filter(visit_record=record).count() == 0


@pytest.mark.django_db
def test_방문_기록에_사진이_5장_있을_때_추가_업로드하면_거부된다(client, make_user, make_event, png_bytes, settings, tmp_path, make_visit, make_visit_photo):
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")

    png_data = png_bytes()
    for i in range(5):
        make_visit_photo(record, filename=f"photo-{i}.png")

    client.force_login(user)
    response = client.post(
        f"/api/visit-records/{record.id}/photos/",
        {"image": SimpleUploadedFile("extra.png", png_data, content_type="image/png")},
    )

    assert response.status_code == 400
    assert VisitRecordPhoto.objects.filter(visit_record=record).count() == 5
    assert response.json()["detail"] == "A visit record can have at most 5 photos."


@pytest.mark.django_db
def test_사진_업로드_중_방문_기록이_동시에_삭제되면_404가_반환된다(client, make_user, make_event, png_bytes, settings, tmp_path, monkeypatch, make_visit):
    """존재 확인과 서비스 호출 사이에 VisitRecord가 삭제되면(TOCTOU 경쟁),
    뷰는 500이 아니라 404를 반환해야 한다.

    순수 서비스 테스트가 아니라 뷰 레이어에 두는 이유: 경쟁 상태를
    archive.views가 임포트한 create_visit_record_photo 참조를 monkeypatch해서
    재현하는데, 그 패치 지점이 여기에만 있기 때문이다.
    """
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")

    from archive import views as archive_views

    original_create_visit_record_photo = archive_views.create_visit_record_photo

    def racing_create_visit_record_photo(*, visit_record, image):
        # 뷰의 존재 확인과 서비스의 select_for_update().get(...) 사이에
        # 동시 삭제가 끼어드는 상황을 재현한다.
        VisitRecord.objects.filter(pk=visit_record.pk).delete()
        return original_create_visit_record_photo(visit_record=visit_record, image=image)

    monkeypatch.setattr(
        archive_views, "create_visit_record_photo", racing_create_visit_record_photo
    )

    client.force_login(user)
    response = client.post(
        f"/api/visit-records/{record.id}/photos/",
        {"image": SimpleUploadedFile("photo.png", png_bytes(), content_type="image/png")},
    )

    assert response.status_code == 404
    assert VisitRecordPhoto.objects.count() == 0


# ---------------------------------------------------------------------------
# INTG-BE-01-VRP-WEB / INTG-BE-04-VRP-WEB (bfcache 중복 생성 계획 §6) — 사진
# 업로드의 client_token 멱등성에 대한 HTTP 경계 계약. 위 INTG-BE-01-VR-WEB와
# 대응한다. 사진 중복 방지 범위는 (user, client_token)이 아니라
# (visit_record, client_token)이다 — 이유는 VisitRecordPhoto의
# UniqueConstraint와 create_visit_record_photo의 독스트링 참조.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_같은_클라이언트_토큰으로_사진_업로드_POST를_두_번_보내면_두_응답_모두_201이고_동일한_id를_반환하며_DB에는_사진이_하나만_생성된다(
    client, make_user, make_event, png_bytes, settings, tmp_path, make_visit
):
    """INTG-BE-01-VRP-WEB: 상한 이하에서 같은 client_token으로 사진 업로드가
    재전송되면(bfcache로 복원된 페이지가 오래된 폼을 재제출하는 경우 등)
    두 번째 행이 생기면 안 된다 — 두 응답 모두 같은 id로 성공하고 행은
    하나만 존재해야 한다."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")
    client_token = str(uuid.uuid4())

    client.force_login(user)
    first_response = client.post(
        f"/api/visit-records/{record.id}/photos/",
        {
            "image": SimpleUploadedFile("first.png", png_bytes(), content_type="image/png"),
            "client_token": client_token,
        },
    )
    second_response = client.post(
        f"/api/visit-records/{record.id}/photos/",
        {
            "image": SimpleUploadedFile("second.png", png_bytes(), content_type="image/png"),
            "client_token": client_token,
        },
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert first_response.json()["id"] == second_response.json()["id"]
    assert VisitRecordPhoto.objects.filter(visit_record=record).count() == 1


@pytest.mark.django_db
def test_상한을_채운_마지막_사진과_같은_클라이언트_토큰으로_사진_업로드_POST를_재전송하면_201이고_동일한_id가_반환된다(
    client, make_user, make_event, png_bytes, settings, tmp_path, make_visit, make_visit_photo
):
    """INTG-BE-04-VRP-WEB: 응답 유실 후 재시도 시나리오 — 클라이언트가
    MAX_PHOTOS_PER_RECORD를 채운 사진의 201 응답을 받지 못해 같은
    client_token으로 재전송한다. 이때도 상한에서 정말 새 사진을 올린 경우의
    400 photo_limit_exceeded가 아니라 201 멱등 재생이어야 한다."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")
    client_token = str(uuid.uuid4())

    # Given: 상한이 이미 찼고, 마지막 직전까지의 사진에는 토큰이 없으며,
    # 상한을 채우는 마지막 사진만 (같은 엔드포인트로) 검증 대상 토큰을 갖고
    # 생성됐다.
    for i in range(MAX_PHOTOS_PER_RECORD - 1):
        make_visit_photo(record, filename=f"photo-{i}.png")

    client.force_login(user)
    first_response = client.post(
        f"/api/visit-records/{record.id}/photos/",
        {
            "image": SimpleUploadedFile("last.png", png_bytes(), content_type="image/png"),
            "client_token": client_token,
        },
    )
    assert first_response.status_code == 201
    assert VisitRecordPhoto.objects.filter(visit_record=record).count() == MAX_PHOTOS_PER_RECORD

    # When: 클라이언트가 `first_response` 응답을 받지 못해 같은 요청을(같은
    # 토큰으로) 그대로 재시도한다.
    retried_response = client.post(
        f"/api/visit-records/{record.id}/photos/",
        {
            "image": SimpleUploadedFile("retry.png", png_bytes(), content_type="image/png"),
            "client_token": client_token,
        },
    )

    # Then: 201, 같은 id, 상한을 넘는 증가 없음 — 진짜 6번째 사진이었다면
    # 받았을 400 photo_limit_exceeded가 아니다.
    assert retried_response.status_code == 201
    assert retried_response.json()["id"] == first_response.json()["id"]
    assert VisitRecordPhoto.objects.filter(visit_record=record).count() == MAX_PHOTOS_PER_RECORD


# ---------------------------------------------------------------------------
# 사진 업로드 스로틀 — 기록당 사진 상한(5장)이 있어 여러 기록에 나눠
# 30장을 채우고 31번째를 확인한다.
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.django_db
def test_사진_업로드_요청이_설정된_한도를_초과하면_429로_제한된다(
    client, make_user, make_event, png_bytes, settings, tmp_path, make_visit
):
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    client.force_login(user)

    # 분당 30건 한도: 기록당 5장 상한이라 기록 6개에 5장씩 채운다.
    records = [
        make_visit(user, event=make_event(title=f"사진 한도 행사 {i}"), visited_on="2026-05-26")
        for i in range(6)
    ]
    for i in range(30):
        record = records[i // MAX_PHOTOS_PER_RECORD]
        response = client.post(
            f"/api/visit-records/{record.id}/photos/",
            {"image": SimpleUploadedFile(f"photo-{i}.png", png_bytes(), content_type="image/png")},
        )
        assert response.status_code == 201, f"upload {i} should succeed"

    over_limit_record = make_visit(user, event=make_event(title="사진 한도 초과 행사"), visited_on="2026-05-26")
    throttled = client.post(
        f"/api/visit-records/{over_limit_record.id}/photos/",
        {"image": SimpleUploadedFile("over-limit.png", png_bytes(), content_type="image/png")},
    )

    assert throttled.status_code == 429
    assert VisitRecordPhoto.objects.count() == 30


# ---------------------------------------------------------------------------
# 사진 삭제 (DELETE /api/visit-records/<record_id>/photos/<photo_id>/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_본인_방문_기록의_사진을_삭제하면_사진이_제거된다(client, make_user, make_event, settings, tmp_path, make_visit, make_visit_photo):
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")
    photo = make_visit_photo(record)

    client.force_login(user)
    response = client.delete(f"/api/visit-records/{record.id}/photos/{photo.id}/")

    assert response.status_code == 204
    assert not VisitRecordPhoto.objects.filter(pk=photo.id).exists()


@pytest.mark.django_db
def test_타인의_방문_기록_사진_삭제를_시도하면_404가_반환되고_사진이_유지된다(client, make_user, make_event, settings, tmp_path, make_visit, make_visit_photo):
    settings.MEDIA_ROOT = str(tmp_path)
    owner = make_user()
    attacker = make_user()
    event = make_event()
    record = make_visit(owner, event=event, visited_on="2026-05-26")
    photo = make_visit_photo(record)

    client.force_login(attacker)
    response = client.delete(f"/api/visit-records/{record.id}/photos/{photo.id}/")

    assert response.status_code == 404
    assert VisitRecordPhoto.objects.filter(pk=photo.id).exists()


# ---------------------------------------------------------------------------
# 레거시 / 보류된 경로는 비활성 상태로 유지된다
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    ["/api/me/visit-records/", "/api/visit-record-photos/", "/api/visit-record-photos/1/"],
    ids=["구_me_방문_기록_목록", "구_사진_컬렉션", "구_사진_상세"],
)
@pytest.mark.django_db
def test_사용되지_않는_레거시_방문_기록_경로에_접근하면_404가_반환된다(client, make_user, path):
    user = make_user()
    client.force_login(user)
    response = client.get(path)
    assert response.status_code == 404
