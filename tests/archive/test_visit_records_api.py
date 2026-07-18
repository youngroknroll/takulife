"""
Active visit-record API tests for the archive app.

All paths are under /api/visit-records/ and /api/visit-records/<pk>/photos/.
Photo upload security: real Pillow-backed ImageField validation, extension
allowlist (jpg/jpeg/png/webp only), 5 MB max, decompression-bomb guard, and
per-record photo cap of 5.
"""

import io
import uuid

import PIL.Image
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from archive.models import UserEventStatus, VisitRecord, VisitRecordPhoto

pytestmark = pytest.mark.web


# ---------------------------------------------------------------------------
# VisitRecord create (POST /api/visit-records/)
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
# Create auto-transitions the status subject to visited (PR-C3 orchestration)
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
# Multiple visits per event are allowed (no unique constraint)
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
# INTG-BE-01-VR-WEB (bfcache duplicate-creation plan §6) — the HTTP boundary
# contract for client_token idempotency on VisitRecord create, mirroring
# INTG-BE-01-CI-WEB in tests/archive/test_collection_items_api.py.
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
# INTG-BE-05-VR (bfcache duplicate-creation plan §6, verification boundary
# "web/slow") — mirrors INTG-BE-05-CI in
# tests/archive/test_collection_items_api.py: the create endpoint must cap
# flood-style repeated POSTs with a 30/minute scoped throttle, distinct from
# the client_token idempotency guard above. Reuses one event across all 30
# creates (multiple visits per event are allowed, proven above) so the
# throttle — not a business-rule rejection — is what stops the 31st request.
# GET (list) must stay unaffected.
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.django_db
def test_방문_기록_생성_요청이_설정된_한도를_초과하면_429로_제한된다(client, make_user, make_event):
    user = make_user()
    event = make_event()
    client.force_login(user)

    # 30/minute budget: 30 creates succeed, the 31st is throttled.
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
# VisitRecord list (GET /api/visit-records/)
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
# VisitRecord detail (GET /api/visit-records/<pk>/)
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
# VisitRecord delete (DELETE /api/visit-records/<pk>/)
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
# VisitRecord update (PATCH /api/visit-records/<pk>/)
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
    # subject stays pinned to the original event; only short_review changed.
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
# Photo upload (POST /api/visit-records/<record_id>/photos/)
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
    """Fake bytes labeled as .jpg must be rejected by Pillow content inspection."""
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
    """Files larger than 5 MB must be rejected with 400."""
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
    """SVG files must be rejected even if Pillow might accept them."""
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
    """A valid BMP renamed with a .png extension must be rejected.

    The extension allowlist alone is attacker-controlled; the real decoded
    Pillow format must be authoritative (S1).
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
    """An image within the per-axis cap but over the total pixel-area cap must be rejected.

    Proves the area guard is independent of both the 5 MB byte cap and the
    per-axis dimension cap (S2). The limit is monkeypatched small to avoid
    allocating a real decompression bomb in CI.
    """
    settings.MEDIA_ROOT = str(tmp_path)
    monkeypatch.setattr("events.image_validation.MAX_IMAGE_PIXELS_LIMIT", 50)
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")

    # 10x10 = 100 px > 50 limit, but each axis (10) is well under MAX_IMAGE_DIMENSION_PX
    # and the byte size is a few hundred bytes.
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
    """The 6th photo for a single record must be rejected (cap is 5)."""
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
    """If the VisitRecord is deleted between the existence check and the
    service call (TOCTOU race), the view must return 404, not 500.

    Stays at the view layer (rather than a pure service test) because the
    race is simulated by monkeypatching archive.views' own imported
    create_visit_record_photo reference — that patch point only exists here.
    """
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")

    from archive import views as archive_views

    original_create_visit_record_photo = archive_views.create_visit_record_photo

    def racing_create_visit_record_photo(*, visit_record, image):
        # Simulate a concurrent delete landing between the view's existence
        # check and the service's select_for_update().get(...).
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
# Photo delete (DELETE /api/visit-records/<record_id>/photos/<photo_id>/)
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
# Legacy / deferred paths remain inactive
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
