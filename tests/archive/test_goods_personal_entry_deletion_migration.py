"""GOODS PersonalEntry 행 삭제 마이그레이션 테스트(컬렉션 도메인 설계안 §3-5 M2,
PR-C4 단계 E, 게이트 후속 M2).

0018 마이그레이션(archive/migrations/0018_remove_goods_personal_entries.py)은
0017이 CollectionItem으로 복사해 둔 GOODS 행을 지우고 PersonalEntry.kind 선택지를
좁힌다. 그 모듈 독스트링의 "PLACE 행은 건드리지 않는다" 주장을 실제로 검증하는
누락된 테스트다(backend-tdd-coach CP13). CP10
(tests/archive/test_visit_record_status_orchestration.py)과 같은 방식으로
마이그레이션 모듈을 임포트해 ``django.apps.apps``(고정된 과거 레지스트리가 아님)로
직접 호출한다.
"""
import importlib

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from archive.models import CollectionItem, PersonalEntry

pytestmark = pytest.mark.contract


def _deletion_migration_module():
    return importlib.import_module("archive.migrations.0018_remove_goods_personal_entries")


def _goods_migration_module():
    return importlib.import_module("archive.migrations.0017_migrate_goods_to_collection_items")


@pytest.mark.django_db
def test_삭제_마이그레이션을_실행하면_GOODS_행은_제거되고_PLACE_행은_보존된다(
    make_user, make_entry
):
    user = make_user()
    place = make_entry(user, kind="place", title="장소")
    goods = PersonalEntry.objects.create(user=user, kind="goods", title="굿즈")

    from django.apps import apps as real_apps

    _deletion_migration_module().delete_goods_personal_entries(real_apps, None)

    assert not PersonalEntry.objects.filter(kind="goods").exists()
    assert PersonalEntry.objects.filter(pk=place.pk).exists()
    assert not PersonalEntry.objects.filter(pk=goods.pk).exists()


@pytest.mark.django_db
def test_삭제_마이그레이션은_사용자별로_GOODS_행만_제거하고_PLACE_행은_보존한다(make_user):
    user_a = make_user()
    user_b = make_user()
    place_a = PersonalEntry.objects.create(user=user_a, kind="place", title="A의 장소")
    goods_a = PersonalEntry.objects.create(user=user_a, kind="goods", title="A의 굿즈")
    place_b = PersonalEntry.objects.create(user=user_b, kind="place", title="B의 장소")
    goods_b = PersonalEntry.objects.create(user=user_b, kind="goods", title="B의 굿즈")

    from django.apps import apps as real_apps

    _deletion_migration_module().delete_goods_personal_entries(real_apps, None)

    remaining = set(PersonalEntry.objects.values_list("pk", flat=True))
    assert remaining == {place_a.pk, place_b.pk}
    assert goods_a.pk not in remaining
    assert goods_b.pk not in remaining


@pytest.mark.django_db
def test_이관_마이그레이션_이후_삭제_마이그레이션을_실행해도_이관된_이미지는_보존된다(
    make_user, png_bytes, settings, tmp_path
):
    """CP13의 본래 의도: 0017이 만든 CollectionItem 이미지 복사본은 0018이 원본
    GOODS 행을 지운 뒤에도 스토리지에서 읽혀야 한다 — 두 마이그레이션은 저장 키를
    공유하지 않으므로(0017의 CP-Image 보증), 원본 삭제가 복사본을 함께 지울 수 없다."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    PersonalEntry.objects.create(
        user=user,
        kind="goods",
        title="이전 대상",
        image=SimpleUploadedFile("goods.png", png_bytes(), content_type="image/png"),
    )

    from django.apps import apps as real_apps

    _goods_migration_module().migrate_goods_to_collection_items(real_apps, None)
    item = CollectionItem.objects.get(user=user)
    storage = item.image.storage
    image_name = item.image.name
    assert storage.exists(image_name)

    _deletion_migration_module().delete_goods_personal_entries(real_apps, None)

    assert not PersonalEntry.objects.filter(kind="goods").exists()
    item.refresh_from_db()
    assert storage.exists(item.image.name)
    assert item.image.name == image_name
