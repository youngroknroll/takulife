"""GOODS PersonalEntry row deletion data migration (collection domain design
plan §3-5 M2, PR-C4 stage E, gate follow-up M2).

Migration 0018 (archive/migrations/0018_remove_goods_personal_entries.py)
deletes the now-redundant original GOODS rows once 0017 has copied them into
CollectionItem, and narrows PersonalEntry.kind's choices. Its module
docstring claims "PLACE rows are never touched" — this file is the missing
test that actually proves that claim (backend-tdd-coach CP13), following the
same repository precedent as CP10
(tests/archive/test_visit_record_status_orchestration.py): import the
migration module and call its function directly against
``django.apps.apps`` (not the frozen historical registry).
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
    """CP13's original intent: the CollectionItem image copy 0017 creates
    must still be readable from storage after 0018 deletes the source GOODS
    row — the two migrations never share a storage key (0017's CP-Image
    guarantee), so deleting the source can never take the copy down with it."""
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
