"""
Active visit-record API tests for the archive app.

All paths are under /api/visit-records/ and /api/visit-records/<pk>/photos/.
Photo upload security: real Pillow-backed ImageField validation, extension
allowlist (jpg/jpeg/png/webp only), 5 MB max, decompression-bomb guard, and
per-record photo cap of 10.
"""

import io

import PIL.Image
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from archive.models import VisitRecord, VisitRecordPhoto


# ---------------------------------------------------------------------------
# VisitRecord create (POST /api/visit-records/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_authenticated_user_can_create_visit_record(client, make_user, make_event):
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
def test_create_visit_record_persisted_under_correct_user(client, make_user, make_event):
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
def test_create_visit_record_rejects_unpublished_event(client, make_user, make_draft_event):
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
def test_create_visit_record_requires_authentication(client, make_event):
    event = make_event()

    response = client.post(
        "/api/visit-records/",
        {"event": event.id, "visited_on": "2026-05-26"},
        content_type="application/json",
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Multiple visits per event are allowed (no unique constraint)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_same_user_can_create_multiple_visit_records_for_same_event(client, make_user, make_event):
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
# VisitRecord list (GET /api/visit-records/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_visit_record_list_scoped_to_current_user(client, make_user, make_event):
    user = make_user()
    other_user = make_user()
    event = make_event()
    owned = VisitRecord.objects.create(user=user, event=event, visited_on="2026-05-26")
    VisitRecord.objects.create(user=other_user, event=event, visited_on="2026-05-27")

    client.force_login(user)
    response = client.get("/api/visit-records/")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {"count", "next", "previous", "results"}
    assert payload["count"] == 1
    assert payload["results"][0]["id"] == owned.id


@pytest.mark.django_db
def test_visit_record_list_paginated(client, make_user, make_event):
    user = make_user()
    event = make_event()
    for i in range(21):
        VisitRecord.objects.create(
            user=user,
            event=event,
            visited_on=f"2026-05-{str(i + 1).zfill(2)}",
        )

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
def test_owner_can_retrieve_visit_record(client, make_user, make_event):
    user = make_user()
    event = make_event()
    record = VisitRecord.objects.create(user=user, event=event, visited_on="2026-05-26")

    client.force_login(user)
    response = client.get(f"/api/visit-records/{record.id}/")

    assert response.status_code == 200
    assert response.json()["id"] == record.id


@pytest.mark.django_db
def test_non_owner_retrieving_visit_record_returns_404(client, make_user, make_event):
    owner = make_user()
    attacker = make_user()
    event = make_event()
    record = VisitRecord.objects.create(user=owner, event=event, visited_on="2026-05-26")

    client.force_login(attacker)
    response = client.get(f"/api/visit-records/{record.id}/")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# VisitRecord delete (DELETE /api/visit-records/<pk>/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_owner_can_delete_visit_record(client, make_user, make_event):
    user = make_user()
    event = make_event()
    record = VisitRecord.objects.create(user=user, event=event, visited_on="2026-05-26")

    client.force_login(user)
    response = client.delete(f"/api/visit-records/{record.id}/")

    assert response.status_code == 204
    assert not VisitRecord.objects.filter(pk=record.id).exists()


@pytest.mark.django_db
def test_non_owner_deleting_visit_record_returns_404(client, make_user, make_event):
    owner = make_user()
    attacker = make_user()
    event = make_event()
    record = VisitRecord.objects.create(user=owner, event=event, visited_on="2026-05-26")

    client.force_login(attacker)
    response = client.delete(f"/api/visit-records/{record.id}/")

    assert response.status_code == 404
    assert VisitRecord.objects.filter(pk=record.id).exists()


# ---------------------------------------------------------------------------
# VisitRecord update (PATCH /api/visit-records/<pk>/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_owner_can_update_visit_record(client, make_user, make_event):
    user = make_user()
    event = make_event()
    record = VisitRecord.objects.create(
        user=user, event=event, visited_on="2026-05-26", short_review="old"
    )

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
def test_update_visit_record_subject_is_read_only(client, make_user, make_event):
    user = make_user()
    event = make_event()
    other_event = make_event()
    record = VisitRecord.objects.create(
        user=user, event=event, visited_on="2026-05-26"
    )

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
def test_non_owner_updating_visit_record_returns_404(client, make_user, make_event):
    owner = make_user()
    attacker = make_user()
    event = make_event()
    record = VisitRecord.objects.create(
        user=owner, event=event, visited_on="2026-05-26", short_review="old"
    )

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
def test_update_visit_record_requires_authentication(client, make_user, make_event):
    user = make_user()
    event = make_event()
    record = VisitRecord.objects.create(
        user=user, event=event, visited_on="2026-05-26"
    )

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
def test_owner_can_upload_photo(client, make_user, make_event, png_bytes, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    event = make_event()
    record = VisitRecord.objects.create(user=user, event=event, visited_on="2026-05-26")

    client.force_login(user)
    response = client.post(
        f"/api/visit-records/{record.id}/photos/",
        {"image": SimpleUploadedFile("photo.png", png_bytes(), content_type="image/png")},
    )

    assert response.status_code == 201
    assert VisitRecordPhoto.objects.filter(visit_record=record).count() == 1


@pytest.mark.django_db
def test_upload_photo_to_other_users_record_returns_404(client, make_user, make_event, png_bytes, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    owner = make_user()
    attacker = make_user()
    event = make_event()
    record = VisitRecord.objects.create(user=owner, event=event, visited_on="2026-05-26")

    client.force_login(attacker)
    response = client.post(
        f"/api/visit-records/{record.id}/photos/",
        {"image": SimpleUploadedFile("photo.png", png_bytes(), content_type="image/png")},
    )

    assert response.status_code == 404
    assert VisitRecordPhoto.objects.count() == 0


@pytest.mark.django_db
def test_upload_missing_image_returns_400(client, make_user, make_event, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    event = make_event()
    record = VisitRecord.objects.create(user=user, event=event, visited_on="2026-05-26")

    client.force_login(user)
    response = client.post(
        f"/api/visit-records/{record.id}/photos/",
        {},
    )

    assert response.status_code == 400
    assert "image" in response.json()


@pytest.mark.django_db
def test_upload_non_image_bytes_rejected_400(client, make_user, make_event, settings, tmp_path):
    """Fake bytes labeled as .jpg must be rejected by Pillow content inspection."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    event = make_event()
    record = VisitRecord.objects.create(user=user, event=event, visited_on="2026-05-26")

    client.force_login(user)
    response = client.post(
        f"/api/visit-records/{record.id}/photos/",
        {"image": SimpleUploadedFile("not_an_image.jpg", b"notanimage", content_type="image/jpeg")},
    )

    assert response.status_code == 400
    assert "image" in response.json()


@pytest.mark.django_db
def test_upload_oversized_file_rejected_400(client, make_user, make_event, png_bytes, settings, tmp_path):
    """Files larger than 5 MB must be rejected with 400."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    event = make_event()
    record = VisitRecord.objects.create(user=user, event=event, visited_on="2026-05-26")

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
def test_upload_disallowed_extension_svg_rejected_400(client, make_user, make_event, settings, tmp_path):
    """SVG files must be rejected even if Pillow might accept them."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    event = make_event()
    record = VisitRecord.objects.create(user=user, event=event, visited_on="2026-05-26")
    svg_content = b"<svg xmlns='http://www.w3.org/2000/svg'><circle r='5'/></svg>"

    client.force_login(user)
    response = client.post(
        f"/api/visit-records/{record.id}/photos/",
        {"image": SimpleUploadedFile("icon.svg", svg_content, content_type="image/svg+xml")},
    )

    assert response.status_code == 400
    assert "image" in response.json()


@pytest.mark.django_db
def test_upload_format_spoofing_bmp_as_png_rejected_400(client, make_user, make_event, settings, tmp_path):
    """A valid BMP renamed with a .png extension must be rejected.

    The extension allowlist alone is attacker-controlled; the real decoded
    Pillow format must be authoritative (S1).
    """
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    event = make_event()
    record = VisitRecord.objects.create(user=user, event=event, visited_on="2026-05-26")

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
def test_upload_pixel_area_bomb_rejected_400(client, make_user, make_event, png_bytes, settings, tmp_path, monkeypatch):
    """An image within the per-axis cap but over the total pixel-area cap must be rejected.

    Proves the area guard is independent of both the 5 MB byte cap and the
    per-axis dimension cap (S2). The limit is monkeypatched small to avoid
    allocating a real decompression bomb in CI.
    """
    settings.MEDIA_ROOT = str(tmp_path)
    monkeypatch.setattr("events.image_validation.MAX_IMAGE_PIXELS_LIMIT", 50)
    user = make_user()
    event = make_event()
    record = VisitRecord.objects.create(user=user, event=event, visited_on="2026-05-26")

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
def test_sixth_photo_upload_rejected_400(client, make_user, make_event, png_bytes, settings, tmp_path):
    """The 6th photo for a single record must be rejected (cap is 5)."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    event = make_event()
    record = VisitRecord.objects.create(user=user, event=event, visited_on="2026-05-26")

    png_data = png_bytes()
    for i in range(5):
        VisitRecordPhoto.objects.create(
            visit_record=record,
            image=SimpleUploadedFile(f"photo-{i}.png", png_data, content_type="image/png"),
        )

    client.force_login(user)
    response = client.post(
        f"/api/visit-records/{record.id}/photos/",
        {"image": SimpleUploadedFile("extra.png", png_data, content_type="image/png")},
    )

    assert response.status_code == 400
    assert VisitRecordPhoto.objects.filter(visit_record=record).count() == 5


# ---------------------------------------------------------------------------
# Photo delete (DELETE /api/visit-records/<record_id>/photos/<photo_id>/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_owner_can_delete_photo(client, make_user, make_event, png_bytes, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    event = make_event()
    record = VisitRecord.objects.create(user=user, event=event, visited_on="2026-05-26")
    photo = VisitRecordPhoto.objects.create(
        visit_record=record,
        image=SimpleUploadedFile("photo.png", png_bytes(), content_type="image/png"),
    )

    client.force_login(user)
    response = client.delete(f"/api/visit-records/{record.id}/photos/{photo.id}/")

    assert response.status_code == 204
    assert not VisitRecordPhoto.objects.filter(pk=photo.id).exists()


@pytest.mark.django_db
def test_non_owner_deleting_photo_returns_404(client, make_user, make_event, png_bytes, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    owner = make_user()
    attacker = make_user()
    event = make_event()
    record = VisitRecord.objects.create(user=owner, event=event, visited_on="2026-05-26")
    photo = VisitRecordPhoto.objects.create(
        visit_record=record,
        image=SimpleUploadedFile("photo.png", png_bytes(), content_type="image/png"),
    )

    client.force_login(attacker)
    response = client.delete(f"/api/visit-records/{record.id}/photos/{photo.id}/")

    assert response.status_code == 404
    assert VisitRecordPhoto.objects.filter(pk=photo.id).exists()


# ---------------------------------------------------------------------------
# Legacy / deferred paths remain inactive
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/api/me/visit-records/", "/api/visit-record-photos/", "/api/visit-record-photos/1/"])
@pytest.mark.django_db
def test_legacy_visit_record_routes_remain_inactive(client, make_user, path):
    user = make_user()
    client.force_login(user)
    response = client.get(path)
    assert response.status_code == 404
