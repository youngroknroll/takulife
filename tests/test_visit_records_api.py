import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from events.models import Event, VisitRecord, VisitRecordPhoto


@pytest.mark.parametrize("path", ["/api/me/visit-records/", "/api/visit-records/"])
@pytest.mark.django_db
def test_archive_visit_record_create_routes_remain_inactive(client, django_user_model, path):
    user = django_user_model.objects.create_user(username="visitor", password="secret")
    event = Event.objects.create(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    client.force_login(user)
    response = client.post(
        path,
        {"event": event.id, "visited_on": "2026-05-26", "short_review": "good"},
        content_type="application/json",
    )

    assert response.status_code == 404


@pytest.mark.parametrize(
    ("path_template", "extra_data"),
    [
        ("/api/me/visit-records/{record_id}/photos/", {}),
        ("/api/visit-record-photos/", {"visit_record": "{record_id}"}),
    ],
)
@pytest.mark.django_db
def test_archive_visit_record_photo_create_routes_remain_inactive(
    client,
    django_user_model,
    settings,
    tmp_path,
    path_template,
    extra_data,
):
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
    path = path_template.format(record_id=record.id)
    request_data = {
        key: (record.id if value == "{record_id}" else value)
        for key, value in extra_data.items()
    }
    request_data["image"] = SimpleUploadedFile("photo.jpg", b"filecontent", content_type="image/jpeg")
    response = client.post(
        path,
        request_data,
    )

    assert response.status_code == 404
    assert VisitRecordPhoto.objects.filter(visit_record=record).count() == 0


@pytest.mark.parametrize(
    "path_template",
    [
        "/api/me/visit-records/{record_id}/photos/{photo_id}/",
        "/api/visit-record-photos/{photo_id}/",
    ],
)
@pytest.mark.django_db
def test_archive_visit_record_photo_delete_routes_remain_inactive(
    client,
    django_user_model,
    settings,
    tmp_path,
    path_template,
):
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
    response = client.delete(path_template.format(record_id=record.id, photo_id=photo.id))

    assert response.status_code == 404
    assert VisitRecordPhoto.objects.filter(pk=photo.id).exists()
