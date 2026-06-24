"""
Active visit-record API tests for the archive app.

All paths are under /api/visit-records/ and /api/visit-records/<pk>/photos/.
Photo upload security: real Pillow-backed ImageField validation, extension
allowlist (jpg/jpeg/png/webp only), 5 MB max, decompression-bomb guard, and
per-record photo cap of 10.
"""

import io
import secrets

import PIL.Image
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from archive.models import VisitRecord, VisitRecordPhoto
from events.models import Event


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_png_bytes(width=10, height=10):
    """Return bytes of a tiny valid PNG via Pillow (for real ImageField validation)."""
    buf = io.BytesIO()
    img = PIL.Image.new("RGB", (width, height), color=(255, 0, 0))
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_user(django_user_model, username=None):
    username = username or f"user_{secrets.token_hex(4)}"
    password = secrets.token_urlsafe(16)
    return django_user_model.objects.create_user(username=username, password=password)


def _make_published_event(title="Published Event"):
    return Event.objects.create(title=title, publish_status=Event.PublishStatus.PUBLISHED)


def _make_draft_event(title="Draft Event"):
    return Event.objects.create(title=title, publish_status=Event.PublishStatus.DRAFT)


# ---------------------------------------------------------------------------
# VisitRecord create (POST /api/visit-records/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_authenticated_user_can_create_visit_record(client, django_user_model):
    user = _make_user(django_user_model)
    event = _make_published_event()

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
def test_create_visit_record_persisted_under_correct_user(client, django_user_model):
    user = _make_user(django_user_model)
    other_user = _make_user(django_user_model)
    event = _make_published_event()

    client.force_login(user)
    client.post(
        "/api/visit-records/",
        {"event": event.id, "visited_on": "2026-05-26"},
        content_type="application/json",
    )

    assert VisitRecord.objects.filter(user=user, event=event).count() == 1
    assert VisitRecord.objects.filter(user=other_user, event=event).count() == 0


@pytest.mark.django_db
def test_create_visit_record_rejects_unpublished_event(client, django_user_model):
    user = _make_user(django_user_model)
    draft_event = _make_draft_event()

    client.force_login(user)
    response = client.post(
        "/api/visit-records/",
        {"event": draft_event.id, "visited_on": "2026-05-26"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert VisitRecord.objects.count() == 0


@pytest.mark.django_db
def test_create_visit_record_requires_authentication(client):
    event = _make_published_event()

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
def test_same_user_can_create_multiple_visit_records_for_same_event(client, django_user_model):
    user = _make_user(django_user_model)
    event = _make_published_event()

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
def test_visit_record_list_scoped_to_current_user(client, django_user_model):
    user = _make_user(django_user_model)
    other_user = _make_user(django_user_model)
    event = _make_published_event()
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
def test_visit_record_list_paginated(client, django_user_model):
    user = _make_user(django_user_model)
    event = _make_published_event()
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
def test_owner_can_retrieve_visit_record(client, django_user_model):
    user = _make_user(django_user_model)
    event = _make_published_event()
    record = VisitRecord.objects.create(user=user, event=event, visited_on="2026-05-26")

    client.force_login(user)
    response = client.get(f"/api/visit-records/{record.id}/")

    assert response.status_code == 200
    assert response.json()["id"] == record.id


@pytest.mark.django_db
def test_non_owner_retrieving_visit_record_returns_404(client, django_user_model):
    owner = _make_user(django_user_model)
    attacker = _make_user(django_user_model)
    event = _make_published_event()
    record = VisitRecord.objects.create(user=owner, event=event, visited_on="2026-05-26")

    client.force_login(attacker)
    response = client.get(f"/api/visit-records/{record.id}/")

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# VisitRecord delete (DELETE /api/visit-records/<pk>/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_owner_can_delete_visit_record(client, django_user_model):
    user = _make_user(django_user_model)
    event = _make_published_event()
    record = VisitRecord.objects.create(user=user, event=event, visited_on="2026-05-26")

    client.force_login(user)
    response = client.delete(f"/api/visit-records/{record.id}/")

    assert response.status_code == 204
    assert not VisitRecord.objects.filter(pk=record.id).exists()


@pytest.mark.django_db
def test_non_owner_deleting_visit_record_returns_404(client, django_user_model):
    owner = _make_user(django_user_model)
    attacker = _make_user(django_user_model)
    event = _make_published_event()
    record = VisitRecord.objects.create(user=owner, event=event, visited_on="2026-05-26")

    client.force_login(attacker)
    response = client.delete(f"/api/visit-records/{record.id}/")

    assert response.status_code == 404
    assert VisitRecord.objects.filter(pk=record.id).exists()


# ---------------------------------------------------------------------------
# Photo upload (POST /api/visit-records/<record_id>/photos/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_owner_can_upload_photo(client, django_user_model, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    user = _make_user(django_user_model)
    event = _make_published_event()
    record = VisitRecord.objects.create(user=user, event=event, visited_on="2026-05-26")

    client.force_login(user)
    response = client.post(
        f"/api/visit-records/{record.id}/photos/",
        {"image": SimpleUploadedFile("photo.png", _make_png_bytes(), content_type="image/png")},
    )

    assert response.status_code == 201
    assert VisitRecordPhoto.objects.filter(visit_record=record).count() == 1


@pytest.mark.django_db
def test_upload_photo_to_other_users_record_returns_404(client, django_user_model, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    owner = _make_user(django_user_model)
    attacker = _make_user(django_user_model)
    event = _make_published_event()
    record = VisitRecord.objects.create(user=owner, event=event, visited_on="2026-05-26")

    client.force_login(attacker)
    response = client.post(
        f"/api/visit-records/{record.id}/photos/",
        {"image": SimpleUploadedFile("photo.png", _make_png_bytes(), content_type="image/png")},
    )

    assert response.status_code == 404
    assert VisitRecordPhoto.objects.count() == 0


@pytest.mark.django_db
def test_upload_missing_image_returns_400(client, django_user_model, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    user = _make_user(django_user_model)
    event = _make_published_event()
    record = VisitRecord.objects.create(user=user, event=event, visited_on="2026-05-26")

    client.force_login(user)
    response = client.post(
        f"/api/visit-records/{record.id}/photos/",
        {},
    )

    assert response.status_code == 400
    assert "image" in response.json()


@pytest.mark.django_db
def test_upload_non_image_bytes_rejected_400(client, django_user_model, settings, tmp_path):
    """Fake bytes labeled as .jpg must be rejected by Pillow content inspection."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = _make_user(django_user_model)
    event = _make_published_event()
    record = VisitRecord.objects.create(user=user, event=event, visited_on="2026-05-26")

    client.force_login(user)
    response = client.post(
        f"/api/visit-records/{record.id}/photos/",
        {"image": SimpleUploadedFile("not_an_image.jpg", b"notanimage", content_type="image/jpeg")},
    )

    assert response.status_code == 400
    assert "image" in response.json()


@pytest.mark.django_db
def test_upload_oversized_file_rejected_400(client, django_user_model, settings, tmp_path):
    """Files larger than 5 MB must be rejected with 400."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = _make_user(django_user_model)
    event = _make_published_event()
    record = VisitRecord.objects.create(user=user, event=event, visited_on="2026-05-26")

    big_png = _make_png_bytes()
    big_content = big_png + b"\x00" * (5 * 1024 * 1024 + 1 - len(big_png))

    client.force_login(user)
    response = client.post(
        f"/api/visit-records/{record.id}/photos/",
        {"image": SimpleUploadedFile("big.png", big_content, content_type="image/png")},
    )

    assert response.status_code == 400
    assert "image" in response.json()


@pytest.mark.django_db
def test_upload_disallowed_extension_svg_rejected_400(client, django_user_model, settings, tmp_path):
    """SVG files must be rejected even if Pillow might accept them."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = _make_user(django_user_model)
    event = _make_published_event()
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
def test_eleventh_photo_upload_rejected_400(client, django_user_model, settings, tmp_path):
    """The 11th photo for a single record must be rejected."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = _make_user(django_user_model)
    event = _make_published_event()
    record = VisitRecord.objects.create(user=user, event=event, visited_on="2026-05-26")

    png_bytes = _make_png_bytes()
    for i in range(10):
        VisitRecordPhoto.objects.create(
            visit_record=record,
            image=SimpleUploadedFile(f"photo-{i}.png", png_bytes, content_type="image/png"),
        )

    client.force_login(user)
    response = client.post(
        f"/api/visit-records/{record.id}/photos/",
        {"image": SimpleUploadedFile("extra.png", png_bytes, content_type="image/png")},
    )

    assert response.status_code == 400
    assert VisitRecordPhoto.objects.filter(visit_record=record).count() == 10


# ---------------------------------------------------------------------------
# Photo delete (DELETE /api/visit-records/<record_id>/photos/<photo_id>/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_owner_can_delete_photo(client, django_user_model, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    user = _make_user(django_user_model)
    event = _make_published_event()
    record = VisitRecord.objects.create(user=user, event=event, visited_on="2026-05-26")
    photo = VisitRecordPhoto.objects.create(
        visit_record=record,
        image=SimpleUploadedFile("photo.png", _make_png_bytes(), content_type="image/png"),
    )

    client.force_login(user)
    response = client.delete(f"/api/visit-records/{record.id}/photos/{photo.id}/")

    assert response.status_code == 204
    assert not VisitRecordPhoto.objects.filter(pk=photo.id).exists()


@pytest.mark.django_db
def test_non_owner_deleting_photo_returns_404(client, django_user_model, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    owner = _make_user(django_user_model)
    attacker = _make_user(django_user_model)
    event = _make_published_event()
    record = VisitRecord.objects.create(user=owner, event=event, visited_on="2026-05-26")
    photo = VisitRecordPhoto.objects.create(
        visit_record=record,
        image=SimpleUploadedFile("photo.png", _make_png_bytes(), content_type="image/png"),
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
def test_legacy_visit_record_routes_remain_inactive(client, django_user_model, path):
    user = _make_user(django_user_model)
    client.force_login(user)
    response = client.get(path)
    assert response.status_code == 404
