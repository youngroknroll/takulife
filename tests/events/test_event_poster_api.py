"""
Staff-only event poster upload/delete API tests.

Endpoint: /api/events/<pk>/poster/
POST  → 200 {"poster_url": "..."}  (staff only)
DELETE → 204                        (staff only)

검증은 events.image_validation.validate_uploaded_image에 맡긴다(방문 기록 사진
업로드와 공유). 여기서는 이미지가 아닌 바이트 한 가지만 대표로 보고, 검증기
전체 커버리지는 test_visit_records_api.py에 있다.
"""

import secrets

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

pytestmark = pytest.mark.web


def _poster_url(pk):
    return f"/api/events/{pk}/poster/"


@pytest.mark.django_db
def test_스태프가_포스터_이미지를_업로드하면_포스터_URL이_응답되고_행사에_저장된다(staff_client, make_event, png_bytes, settings, tmp_path):
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
    assert payload["poster_url"]

    event.refresh_from_db()
    assert event.poster_image


@pytest.mark.django_db
def test_스태프가_아닌_로그인_사용자의_포스터_업로드는_403으로_거부된다(client, make_user, make_event, png_bytes, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    event = make_event(official_url=f"https://example.com/{secrets.token_hex(4)}")

    client.force_login(user)
    response = client.post(
        _poster_url(event.pk),
        {"image": SimpleUploadedFile("poster.png", png_bytes(color=(100, 150, 200)), content_type="image/png")},
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_로그인하지_않은_사용자의_포스터_업로드는_401이_아닌_403으로_거부된다(client, make_event, png_bytes, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    event = make_event(official_url=f"https://example.com/{secrets.token_hex(4)}")

    response = client.post(
        _poster_url(event.pk),
        {"image": SimpleUploadedFile("poster.png", png_bytes(color=(100, 150, 200)), content_type="image/png")},
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_존재하지_않는_행사에_포스터를_업로드하면_404를_반환한다(staff_client, png_bytes, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)

    _, client = staff_client()
    response = client.post(
        _poster_url(99999),
        {"image": SimpleUploadedFile("poster.png", png_bytes(color=(100, 150, 200)), content_type="image/png")},
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_미게시_행사에_포스터를_업로드하면_404를_반환한다(staff_client, make_draft_event, png_bytes, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    event = make_draft_event(title="Draft Event", official_url=f"https://example.com/draft-{secrets.token_hex(4)}")

    _, client = staff_client()
    response = client.post(
        _poster_url(event.pk),
        {"image": SimpleUploadedFile("poster.png", png_bytes(color=(100, 150, 200)), content_type="image/png")},
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_이미지가_아닌_바이트를_업로드하면_400과_함께_image_오류가_반환된다(staff_client, make_event, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    event = make_event(official_url=f"https://example.com/{secrets.token_hex(4)}")

    _, client = staff_client()
    response = client.post(
        _poster_url(event.pk),
        {"image": SimpleUploadedFile("not_an_image.jpg", b"notanimage", content_type="image/jpeg")},
    )

    assert response.status_code == 400
    assert "image" in response.json()


@pytest.mark.django_db
def test_스태프가_포스터를_삭제하면_204와_함께_이미지가_비워진다(staff_client, make_event, png_bytes, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    event = make_event(official_url=f"https://example.com/{secrets.token_hex(4)}")

    _, client = staff_client()
    client.post(
        _poster_url(event.pk),
        {"image": SimpleUploadedFile("poster.png", png_bytes(color=(100, 150, 200)), content_type="image/png")},
    )

    response = client.delete(_poster_url(event.pk))

    assert response.status_code == 204
    event.refresh_from_db()
    assert not event.poster_image


@pytest.mark.django_db
def test_포스터를_다시_업로드하면_기존_이미지가_새_이미지로_교체된다(staff_client, make_event, png_bytes, settings, tmp_path):
    settings.MEDIA_ROOT = str(tmp_path)
    event = make_event(official_url=f"https://example.com/{secrets.token_hex(4)}")

    _, client = staff_client()

    client.post(
        _poster_url(event.pk),
        {"image": SimpleUploadedFile("poster1.png", png_bytes(color=(100, 150, 200)), content_type="image/png")},
    )
    event.refresh_from_db()
    first_name = event.poster_image.name

    client.post(
        _poster_url(event.pk),
        {"image": SimpleUploadedFile("poster2.png", png_bytes(color=(100, 150, 200)), content_type="image/png")},
    )
    event.refresh_from_db()
    second_name = event.poster_image.name

    assert second_name != first_name
