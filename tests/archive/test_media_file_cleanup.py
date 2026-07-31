"""삭제 시 미디어 파일 정리 테스트.

VisitRecordPhoto를 삭제(직접 또는 VisitRecord CASCADE로)하거나 이미지가 있는
PersonalEntry를 삭제하면 스토리지의 실제 파일도 함께 지워야 한다. 정리는 삭제
트랜잭션이 실제로 커밋된 뒤에만 일어나야 하므로(transaction.on_commit,
best-effort), 롤백된 삭제가 아직 남아 있어야 할 파일을 지우는 일은 없어야 한다.
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
    """삭제 트랜잭션이 롤백되면 on_commit 훅이 절대 실행되지 않아야 하므로
    파일이 스토리지에 그대로 남아 있어야 한다."""
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
    """§6-b 유예 사항(C4 게이트 M4): CollectionItem에는 post_delete 이미지 정리
    리시버가 없었다 — C5가 CollectionItem 삭제 API/애플리케이션 경로를 추가하면서
    이 공백이 비로소 드러났다."""
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
