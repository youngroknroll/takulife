"""Account deletion (accounts.views.delete_account).

GET /accounts/delete/ renders a password-reconfirm form (login required).
POST verifies the current password before deleting the account; owned
archive data and media files cascade via existing FK on_delete/signals
wiring (see archive/models.py, archive/signals.py) — this view does not
re-implement that cleanup, it only orchestrates the password check, the
delete, and ending the session.
"""
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import User
from archive.models import PersonalEntry, VisitRecord, VisitRecordPhoto

DELETE_URL = "/accounts/delete/"


@pytest.mark.django_db
def test_anonymous_get_redirects_to_login(client):
    response = client.get(DELETE_URL)

    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_authenticated_get_renders_confirm_form(client, make_user, valid_password):
    user = make_user(password=valid_password)
    client.force_login(user)

    response = client.get(DELETE_URL)

    assert response.status_code == 200


@pytest.mark.django_db
def test_wrong_password_does_not_delete_the_account(client, make_user, valid_password):
    user = make_user(password=valid_password)
    client.force_login(user)

    response = client.post(DELETE_URL, {"password": "definitely-wrong"})

    assert response.status_code == 200
    assert User.objects.filter(pk=user.pk).exists()


@pytest.mark.django_db
def test_correct_password_deletes_user_owned_data_and_media(
    client, make_user, valid_password, png_bytes, settings, tmp_path, django_capture_on_commit_callbacks
):
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user(password=valid_password)
    entry = PersonalEntry.objects.create(
        user=user,
        kind=PersonalEntry.Kind.PLACE,
        title="탈퇴 테스트 항목",
        image=SimpleUploadedFile("cover.png", png_bytes(), content_type="image/png"),
    )
    storage = entry.image.storage
    file_name = entry.image.name
    assert storage.exists(file_name)

    client.force_login(user)
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(DELETE_URL, {"password": valid_password})

    assert response.status_code == 302
    assert not User.objects.filter(pk=user.pk).exists()
    assert not PersonalEntry.objects.filter(pk=entry.pk).exists()
    assert not storage.exists(file_name)


@pytest.mark.django_db
def test_correct_password_deletes_second_degree_cascade_photo_and_media(
    client,
    make_user,
    make_event,
    valid_password,
    png_bytes,
    settings,
    tmp_path,
    django_capture_on_commit_callbacks,
):
    """User -> VisitRecord (1st-degree CASCADE) -> VisitRecordPhoto
    (2nd-degree CASCADE) must still fire archive.signals' post_delete file
    cleanup — the 1st-degree PersonalEntry path is already covered by
    test_correct_password_deletes_user_owned_data_and_media above."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user(password=valid_password)
    event = make_event()
    record = VisitRecord.objects.create(user=user, event=event, visited_on="2026-05-26")
    photo = VisitRecordPhoto.objects.create(
        visit_record=record,
        image=SimpleUploadedFile("photo.png", png_bytes(), content_type="image/png"),
    )
    storage = photo.image.storage
    file_name = photo.image.name
    assert storage.exists(file_name)

    client.force_login(user)
    with django_capture_on_commit_callbacks(execute=True):
        response = client.post(DELETE_URL, {"password": valid_password})

    assert response.status_code == 302
    assert not VisitRecordPhoto.objects.filter(pk=photo.pk).exists()
    assert not storage.exists(file_name)


@pytest.mark.django_db
def test_correct_password_ends_the_session_immediately(client, make_user, valid_password):
    user = make_user(password=valid_password)
    client.force_login(user)

    client.post(DELETE_URL, {"password": valid_password})

    # The browser still holds the old session cookie, but the session was
    # flushed server-side — a protected page must bounce to login.
    response = client.get("/archive/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


@pytest.mark.django_db
def test_deleted_account_can_no_longer_log_in(client, make_user, valid_password):
    user = make_user(email="leaving@example.com", password=valid_password)
    client.force_login(user)
    client.post(DELETE_URL, {"password": valid_password})

    login_response = client.post(
        "/accounts/login/",
        {"login": "leaving@example.com", "password": valid_password},
    )

    assert login_response.status_code == 200  # form re-rendered, not authenticated
    archive_response = client.get("/archive/")
    assert archive_response.status_code == 302
    assert "/accounts/login/" in archive_response["Location"]
