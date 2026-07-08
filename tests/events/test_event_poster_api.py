"""
Staff-only event poster upload/delete API tests.

Endpoint: /api/events/<pk>/poster/
POST  → 200 {"poster_url": "..."}  (staff only)
DELETE → 204                        (staff only)

Validation is delegated to events.image_validation.validate_uploaded_image
(shared with visit-record photo upload). Only a representative non-image bytes
case is tested here; full validator coverage lives in test_visit_records_api.py.
"""

import secrets

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _poster_url(pk):
    return f"/api/events/{pk}/poster/"


# ---------------------------------------------------------------------------
# POST: staff can upload a poster
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_staff_upload_poster_returns_200_with_poster_url(staff_client, make_event, png_bytes, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    event = make_event(official_url=f"https://example.com/{secrets.token_hex(4)}")

    _, client = staff_client()
    response = client.post(
        _poster_url(event.pk),
        {"image": SimpleUploadedFile("poster.png", png_bytes(color=(100, 150, 200)), content_type="image/png")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "poster_url" in payload
    assert payload["poster_url"]  # non-empty

    event.refresh_from_db()
    assert event.poster_image  # truthy (field has a file)


# ---------------------------------------------------------------------------
# POST: non-staff authenticated user gets 403
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_non_staff_upload_poster_returns_403(client, make_user, make_event, png_bytes, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    event = make_event(official_url=f"https://example.com/{secrets.token_hex(4)}")

    client.force_login(user)
    response = client.post(
        _poster_url(event.pk),
        {"image": SimpleUploadedFile("poster.png", png_bytes(color=(100, 150, 200)), content_type="image/png")},
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# POST: anonymous user gets 403 (not 401)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_anonymous_upload_poster_returns_403(client, make_event, png_bytes, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    event = make_event(official_url=f"https://example.com/{secrets.token_hex(4)}")

    response = client.post(
        _poster_url(event.pk),
        {"image": SimpleUploadedFile("poster.png", png_bytes(color=(100, 150, 200)), content_type="image/png")},
    )

    assert response.status_code == 403


# ---------------------------------------------------------------------------
# POST: nonexistent event gets 404
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_upload_poster_nonexistent_event_returns_404(staff_client, png_bytes, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)

    _, client = staff_client()
    response = client.post(
        _poster_url(99999),
        {"image": SimpleUploadedFile("poster.png", png_bytes(color=(100, 150, 200)), content_type="image/png")},
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST: draft event gets 404
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_upload_poster_to_draft_event_returns_404(staff_client, make_draft_event, png_bytes, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    event = make_draft_event(title="Draft Event", official_url=f"https://example.com/draft-{secrets.token_hex(4)}")

    _, client = staff_client()
    response = client.post(
        _poster_url(event.pk),
        {"image": SimpleUploadedFile("poster.png", png_bytes(color=(100, 150, 200)), content_type="image/png")},
    )

    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST: non-image bytes get 400 with "image" key in body
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_upload_non_image_bytes_returns_400(staff_client, make_event, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    event = make_event(official_url=f"https://example.com/{secrets.token_hex(4)}")

    _, client = staff_client()
    response = client.post(
        _poster_url(event.pk),
        {"image": SimpleUploadedFile("not_an_image.jpg", b"notanimage", content_type="image/jpeg")},
    )

    assert response.status_code == 400
    assert "image" in response.json()


# ---------------------------------------------------------------------------
# DELETE: staff can delete a poster → 204 and poster_image is cleared
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_staff_delete_poster_returns_204_and_clears_image(staff_client, make_event, png_bytes, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    event = make_event(official_url=f"https://example.com/{secrets.token_hex(4)}")

    _, client = staff_client()
    # First upload
    client.post(
        _poster_url(event.pk),
        {"image": SimpleUploadedFile("poster.png", png_bytes(color=(100, 150, 200)), content_type="image/png")},
    )

    # Then delete
    response = client.delete(_poster_url(event.pk))

    assert response.status_code == 204
    event.refresh_from_db()
    assert not event.poster_image  # field cleared


# ---------------------------------------------------------------------------
# POST second upload replaces first (poster_image.name changes)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_second_upload_replaces_first_poster(staff_client, make_event, png_bytes, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    event = make_event(official_url=f"https://example.com/{secrets.token_hex(4)}")

    _, client = staff_client()

    # First upload
    client.post(
        _poster_url(event.pk),
        {"image": SimpleUploadedFile("poster1.png", png_bytes(color=(100, 150, 200)), content_type="image/png")},
    )
    event.refresh_from_db()
    first_name = event.poster_image.name

    # Second upload
    client.post(
        _poster_url(event.pk),
        {"image": SimpleUploadedFile("poster2.png", png_bytes(color=(100, 150, 200)), content_type="image/png")},
    )
    event.refresh_from_db()
    second_name = event.poster_image.name

    assert second_name != first_name
