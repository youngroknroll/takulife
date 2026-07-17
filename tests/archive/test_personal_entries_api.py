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
    assert entry.user == user  # owner taken from the request, not the payload


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
    """A private item must not leak into the public Event catalog API (SSR
    half split to tests/events/test_event_list_view.py)."""
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
def test_굿즈_종류로_개인_항목을_등록하면_거부된다(client, make_user):
    """GOODS is no longer creatable via PersonalEntry (collection domain plan
    §3-3) — goods live in the dedicated CollectionItem domain instead."""
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
    """goods is gone from the model's Kind enum (collection domain plan §3-5
    M2) — the serializer's auto-generated kind ChoiceField must reflect that,
    not just the (now-unreachable) validate_kind guard."""
    from archive.serializers import PersonalEntrySerializer

    assert "goods" not in dict(PersonalEntrySerializer().fields["kind"].choices)


# ---------------------------------------------------------------------------
# image upload — must share the hardened guard with visit photos
# ---------------------------------------------------------------------------


@pytest.mark.web
@pytest.mark.django_db
def test_이미지가_아닌_바이트를_이미지로_업로드하면_거부된다(client, make_user, settings, tmp_path):
    """Fake bytes labeled as .jpg must be rejected by Pillow content inspection."""
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


@pytest.mark.web
@pytest.mark.django_db
def test_SVG_파일을_이미지로_업로드하면_거부된다(client, make_user, settings, tmp_path):
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
