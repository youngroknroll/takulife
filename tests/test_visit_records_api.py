import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from events.models import Event, VisitRecord, VisitRecordPhoto


@pytest.mark.django_db
def test_logged_in_user_can_create_visit_record(client, django_user_model):
    user = django_user_model.objects.create_user(username="visitor", password="secret")
    event = Event.objects.create(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    client.force_login(user)
    response = client.post(
        "/api/me/visit-records/",
        {"event": event.id, "visited_on": "2026-05-26", "short_review": "good"},
        content_type="application/json",
    )

    assert response.status_code == 201


@pytest.mark.django_db
def test_logged_in_user_can_attach_photo_to_visit_record(client, django_user_model, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    user = django_user_model.objects.create_user(username="photo-owner", password="secret")
    event = Event.objects.create(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)
    record = VisitRecord.objects.create(
        user=user,
        event=event,
        visited_on="2026-05-26",
        short_review="good",
    )

    client.force_login(user)
    response = client.post(
        f"/api/me/visit-records/{record.id}/photos/",
        {"image": SimpleUploadedFile("photo.jpg", b"filecontent", content_type="image/jpeg")},
    )

    assert response.status_code == 201
    assert VisitRecordPhoto.objects.filter(visit_record=record).count() == 1


@pytest.mark.django_db
def test_logged_in_user_can_delete_own_visit_record_photo(client, django_user_model, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    user = django_user_model.objects.create_user(username="photo-deleter", password="secret")
    event = Event.objects.create(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)
    record = VisitRecord.objects.create(
        user=user,
        event=event,
        visited_on="2026-05-26",
        short_review="good",
    )
    photo = VisitRecordPhoto.objects.create(
        visit_record=record,
        image=SimpleUploadedFile("photo.jpg", b"filecontent", content_type="image/jpeg"),
    )

    client.force_login(user)
    response = client.delete(f"/api/me/visit-records/{record.id}/photos/{photo.id}/")

    assert response.status_code == 204
    assert not VisitRecordPhoto.objects.filter(pk=photo.id).exists()
