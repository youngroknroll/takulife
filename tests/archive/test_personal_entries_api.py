"""Tests for the PersonalEntry API — user-owned, private, unofficial archive
items, owner-scoped. PersonalEntry is never part of the public catalog.

  POST   /api/personal-entries/        → 201 (owner = request.user)
  GET    /api/personal-entries/        → paginated list (user-scoped)
  GET    /api/personal-entries/<id>/   → 200 or 404
  DELETE /api/personal-entries/<id>/   → 204 or 404
"""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from archive.models import PersonalEntry


@pytest.mark.django_db
def test_create_personal_entry_returns_201_and_sets_owner(client, make_user):
    user = make_user(username="pe-create")

    client.force_login(user)
    response = client.post(
        "/api/personal-entries/",
        {"kind": "goods", "title": "내가 산 굿즈", "memo": "중고 득템"},
        content_type="application/json",
    )

    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "내가 산 굿즈"
    assert data["kind"] == "goods"
    entry = PersonalEntry.objects.get(id=data["id"])
    assert entry.user == user  # owner taken from the request, not the payload


@pytest.mark.django_db
def test_personal_entry_list_is_user_scoped(client, make_user, make_entry):
    user = make_user(username="pe-scope")
    other = make_user(username="pe-scope-other")
    make_entry(user, kind="place", title="Mine")
    make_entry(other, kind="place", title="Theirs")

    client.force_login(user)
    response = client.get("/api/personal-entries/")

    assert response.status_code == 200
    titles = [row["title"] for row in response.json()["results"]]
    assert titles == ["Mine"]


@pytest.mark.django_db
def test_personal_entry_requires_authentication(client):
    response = client.get("/api/personal-entries/")
    assert response.status_code in (401, 403)


@pytest.mark.django_db
def test_personal_entry_never_appears_in_public_api_catalog(client, make_user, make_entry):
    """A private item must not leak into the public Event catalog API (SSR
    half split to tests/events/test_event_list_view.py)."""
    user = make_user(username="pe-leak")
    make_entry(user, kind="place", title="PRIVATE_LEAK_CANARY")

    client.force_login(user)
    api = client.get("/api/events/")

    assert api.status_code == 200
    assert "PRIVATE_LEAK_CANARY" not in api.content.decode()


@pytest.mark.django_db
def test_cannot_delete_another_users_personal_entry(client, make_user, make_entry):
    user = make_user(username="pe-del")
    other = make_user(username="pe-del-other")
    theirs = make_entry(other, kind="place", title="Theirs")

    client.force_login(user)
    response = client.delete(f"/api/personal-entries/{theirs.id}/")

    assert response.status_code == 404
    assert PersonalEntry.objects.filter(id=theirs.id).exists()


# ---------------------------------------------------------------------------
# image upload — must share the hardened guard with visit photos
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_personal_entry_rejects_non_image_bytes(client, make_user, settings, tmp_path):
    """Fake bytes labeled as .jpg must be rejected by Pillow content inspection."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user(username="pe-img-fake")

    client.force_login(user)
    response = client.post(
        "/api/personal-entries/",
        {
            "kind": "goods",
            "title": "스푸핑 이미지",
            "image": SimpleUploadedFile(
                "not_an_image.jpg", b"notanimage", content_type="image/jpeg"
            ),
        },
    )

    assert response.status_code == 400
    assert "image" in response.json()
    assert not PersonalEntry.objects.filter(title="스푸핑 이미지").exists()


@pytest.mark.django_db
def test_create_personal_entry_rejects_oversized_image(client, make_user, png_bytes, settings, tmp_path):
    """Images larger than 5 MB must be rejected with 400 (decompression-bomb guard)."""
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


@pytest.mark.django_db
def test_create_personal_entry_rejects_svg(client, make_user, settings, tmp_path):
    """SVG files must be rejected even if Pillow might accept them."""
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
