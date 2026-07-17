"""Media file cleanup on delete.

Deleting a VisitRecordPhoto (directly or via VisitRecord CASCADE) or a
PersonalEntry with an image must also remove the underlying file from
storage. Cleanup must only happen once the deleting transaction actually
commits (best-effort, via transaction.on_commit) so a rolled-back delete
never loses a file that a caller expected to still be there.
"""

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction

import pytest

from archive.models import CollectionItem, PersonalEntry, VisitRecordPhoto

pytestmark = pytest.mark.slow


@pytest.mark.django_db
def test_방문_사진을_삭제하면_스토리지에서_실제_파일도_제거된다(client, make_user, make_event, settings, tmp_path, django_capture_on_commit_callbacks, make_visit, make_visit_photo):
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")
    photo = make_visit_photo(record)
    storage = photo.image.storage
    file_name = photo.image.name
    assert storage.exists(file_name)

    client.force_login(user)
    with django_capture_on_commit_callbacks(execute=True):
        response = client.delete(f"/api/visit-records/{record.id}/photos/{photo.id}/")

    assert response.status_code == 204
    assert not storage.exists(file_name)


@pytest.mark.django_db
def test_방문_기록을_삭제하면_연쇄로_사진_파일도_제거된다(make_user, make_event, settings, tmp_path, django_capture_on_commit_callbacks, make_visit, make_visit_photo):
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")
    photo = make_visit_photo(record)
    storage = photo.image.storage
    file_name = photo.image.name
    assert storage.exists(file_name)

    with django_capture_on_commit_callbacks(execute=True):
        record.delete()

    assert not storage.exists(file_name)


@pytest.mark.django_db
def test_사진_삭제_트랜잭션이_롤백되면_파일이_보존된다(make_user, make_event, settings, tmp_path, django_capture_on_commit_callbacks, make_visit, make_visit_photo):
    """If the deleting transaction rolls back, the on_commit hook must never
    fire, so the file must remain in storage."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")
    photo = make_visit_photo(record)
    storage = photo.image.storage
    file_name = photo.image.name
    photo_pk = photo.pk
    assert storage.exists(file_name)

    class _Boom(Exception):
        pass

    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(_Boom):
            with transaction.atomic():
                photo.delete()
                raise _Boom

    assert VisitRecordPhoto.objects.filter(pk=photo_pk).exists()
    assert storage.exists(file_name)


@pytest.mark.django_db
def test_개인_항목을_삭제하면_이미지_파일도_제거된다(make_user, png_bytes, settings, tmp_path, django_capture_on_commit_callbacks, make_entry):
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    entry = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="unofficial cafe", image=SimpleUploadedFile("cover.png", png_bytes(), content_type="image/png"))
    storage = entry.image.storage
    file_name = entry.image.name
    assert storage.exists(file_name)

    with django_capture_on_commit_callbacks(execute=True):
        entry.delete()

    assert not storage.exists(file_name)


@pytest.mark.django_db
def test_컬렉션_아이템을_삭제하면_이미지_파일도_제거된다(
    make_user, png_bytes, settings, tmp_path, django_capture_on_commit_callbacks, make_collection_item
):
    """§6-b Deferred (C4 gate M4): CollectionItem had no post_delete image
    cleanup receiver — this gap only became reachable once C5 added a
    delete API/application path for CollectionItem."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    item = make_collection_item(
        user,
        name="이미지 있는 굿즈",
        image=SimpleUploadedFile("cover.png", png_bytes(), content_type="image/png"),
    )
    storage = item.image.storage
    file_name = item.image.name
    assert storage.exists(file_name)

    with django_capture_on_commit_callbacks(execute=True):
        item.delete()

    assert not storage.exists(file_name)
