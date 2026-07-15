"""GOODS PersonalEntry -> CollectionItem data migration (collection domain
design plan §3-5, PR-C4 stage C).

Follows the CP10 repository precedent
(tests/archive/test_visit_record_status_orchestration.py) for testing a
RunPython data migration: import the migration module and call its function
directly against ``django.apps.apps`` (not the frozen historical registry),
so the test exercises the exact function ``manage.py migrate`` would run.

Deliberately builds test rows with the literal string "goods" instead of
``PersonalEntry.Kind.GOODS`` — the enum member is removed in a later commit
of this same track (§3-5 M2) and this file must not need to change then.
"""
import importlib

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from archive.models import CollectionItem, EventInterest, PersonalEntry, UserEventStatus, VisitRecord


def _migration_module():
    return importlib.import_module(
        "archive.migrations.0017_migrate_goods_to_collection_items"
    )


def _make_goods(user, **kwargs):
    kwargs.setdefault("title", "굿즈 항목")
    return PersonalEntry.objects.create(user=user, kind="goods", **kwargs)


# ---------------------------------------------------------------------------
# Field mapping
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_migrates_basic_fields_with_matching_category_label(make_user):
    user = make_user()
    entry = _make_goods(
        user,
        title="최애 키링",
        work_title="최애의 아이2",
        category="키링",
        location_name="서울 성수동 팝업",
        memo="한정판",
    )

    from django.apps import apps as real_apps

    _migration_module().migrate_goods_to_collection_items(real_apps, None)

    item = CollectionItem.objects.get(user=user)
    assert item.name == "최애 키링"
    assert item.work_title == "최애의 아이2"
    assert item.memo == "한정판"
    assert item.acquisition_source == "서울 성수동 팝업"
    assert item.item_type == "keyring"
    assert item.quantity == 1
    assert item.tradeable_quantity == 0
    assert item.is_wanted is False
    assert item.visibility == "private"
    assert item.event is None
    assert item.visit_record is None
    assert item.acquired_on is None


@pytest.mark.django_db
def test_maps_category_slug_directly(make_user):
    user = make_user()
    _make_goods(user, category="badge")

    from django.apps import apps as real_apps

    _migration_module().migrate_goods_to_collection_items(real_apps, None)

    item = CollectionItem.objects.get(user=user)
    assert item.item_type == "badge"


@pytest.mark.django_db
def test_unmatched_category_maps_to_etc(make_user):
    user = make_user()
    _make_goods(user, category="완전히 다른 분류")

    from django.apps import apps as real_apps

    _migration_module().migrate_goods_to_collection_items(real_apps, None)

    item = CollectionItem.objects.get(user=user)
    assert item.item_type == "etc"


@pytest.mark.django_db
def test_blank_category_maps_to_etc(make_user):
    user = make_user()
    _make_goods(user, category="")

    from django.apps import apps as real_apps

    _migration_module().migrate_goods_to_collection_items(real_apps, None)

    item = CollectionItem.objects.get(user=user)
    assert item.item_type == "etc"


# ---------------------------------------------------------------------------
# Defensive failure — abort the entire run, no partial commit
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_blocked_by_visit_record_reference_aborts_entire_run(make_user):
    user = make_user()
    blocked = _make_goods(user, title="차단 대상")
    visit = VisitRecord.objects.create(user=user, personal_entry=blocked, visited_on="2026-07-15")
    clean = _make_goods(user, title="정상 대상")

    from django.apps import apps as real_apps

    with pytest.raises(Exception) as exc_info:
        _migration_module().migrate_goods_to_collection_items(real_apps, None)

    message = str(exc_info.value)
    assert f"PersonalEntry(id={blocked.id})" in message
    assert f"VisitRecord(id={visit.id})" in message or str(visit.id) in message
    # All-or-nothing: the otherwise-valid "clean" row must not be migrated either.
    assert CollectionItem.objects.count() == 0
    assert clean.id is not None  # sanity: clean row is untouched, still present


@pytest.mark.django_db
def test_blocked_by_event_interest_reference(make_user):
    user = make_user()
    blocked = _make_goods(user)
    interest = EventInterest.objects.create(user=user, personal_entry=blocked)

    from django.apps import apps as real_apps

    with pytest.raises(Exception) as exc_info:
        _migration_module().migrate_goods_to_collection_items(real_apps, None)

    message = str(exc_info.value)
    assert f"PersonalEntry(id={blocked.id})" in message
    assert str(interest.id) in message
    assert CollectionItem.objects.count() == 0


@pytest.mark.django_db
def test_blocked_by_user_event_status_reference(make_user):
    user = make_user()
    blocked = _make_goods(user)
    status_row = UserEventStatus.objects.create(user=user, personal_entry=blocked, status="planned")

    from django.apps import apps as real_apps

    with pytest.raises(Exception) as exc_info:
        _migration_module().migrate_goods_to_collection_items(real_apps, None)

    message = str(exc_info.value)
    assert f"PersonalEntry(id={blocked.id})" in message
    assert str(status_row.id) in message
    assert CollectionItem.objects.count() == 0


@pytest.mark.django_db
def test_blocked_by_nonempty_url(make_user):
    user = make_user()
    blocked = _make_goods(user, url="https://example.com/goods")

    from django.apps import apps as real_apps

    with pytest.raises(Exception) as exc_info:
        _migration_module().migrate_goods_to_collection_items(real_apps, None)

    assert f"PersonalEntry(id={blocked.id})" in str(exc_info.value)
    assert CollectionItem.objects.count() == 0


@pytest.mark.django_db
def test_blocked_by_nonempty_region(make_user):
    user = make_user()
    blocked = _make_goods(user, region="seoul")

    from django.apps import apps as real_apps

    with pytest.raises(Exception) as exc_info:
        _migration_module().migrate_goods_to_collection_items(real_apps, None)

    assert f"PersonalEntry(id={blocked.id})" in str(exc_info.value)
    assert CollectionItem.objects.count() == 0


@pytest.mark.django_db
def test_blocked_by_submitted_promotion_status(make_user):
    user = make_user()
    blocked = _make_goods(user, promotion_status="submitted")

    from django.apps import apps as real_apps

    with pytest.raises(Exception) as exc_info:
        _migration_module().migrate_goods_to_collection_items(real_apps, None)

    assert f"PersonalEntry(id={blocked.id})" in str(exc_info.value)
    assert CollectionItem.objects.count() == 0


# ---------------------------------------------------------------------------
# CP-Image — the migrated CollectionItem gets its own physically independent
# file, so PersonalEntry's post_delete storage cleanup can never silently
# wipe the migrated copy (archive/signals.py).
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_migrated_image_is_a_physically_independent_copy(
    make_user, png_bytes, settings, tmp_path, django_capture_on_commit_callbacks
):
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    entry = _make_goods(
        user,
        image=SimpleUploadedFile("goods.png", png_bytes(), content_type="image/png"),
    )
    storage = entry.image.storage
    original_name = entry.image.name
    assert storage.exists(original_name)

    from django.apps import apps as real_apps

    _migration_module().migrate_goods_to_collection_items(real_apps, None)

    item = CollectionItem.objects.get(user=user)

    # (1) distinct storage key — never the same physical file as the source.
    assert item.image.name != original_name

    # (2)+(3) force the PersonalEntry post_delete signal to actually fire by
    # deleting the *real* (non-historical) row, then prove the signal really
    # ran by asserting the original file is gone.
    real_entry = PersonalEntry.objects.get(pk=entry.pk)
    with django_capture_on_commit_callbacks(execute=True):
        real_entry.delete()
    assert storage.exists(original_name) is False

    # (4) the migrated copy survives the source row's deletion untouched.
    item.refresh_from_db()
    assert storage.exists(item.image.name) is True


@pytest.mark.django_db
def test_entry_without_image_migrates_without_error(make_user):
    user = make_user()
    _make_goods(user)

    from django.apps import apps as real_apps

    _migration_module().migrate_goods_to_collection_items(real_apps, None)

    item = CollectionItem.objects.get(user=user)
    assert not item.image


# ---------------------------------------------------------------------------
# Multi-user / multi-row reconciliation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_multiple_users_get_one_to_one_owner_scoped_copies(make_user):
    user_a = make_user()
    user_b = make_user()
    entry_a = _make_goods(user_a, title="A의 굿즈")
    entry_b = _make_goods(user_b, title="B의 굿즈")

    from django.apps import apps as real_apps

    _migration_module().migrate_goods_to_collection_items(real_apps, None)

    assert CollectionItem.objects.count() == 2
    item_a = CollectionItem.objects.get(user=user_a)
    item_b = CollectionItem.objects.get(user=user_b)
    assert item_a.name == entry_a.title
    assert item_b.name == entry_b.title
    assert item_a.user_id == user_a.id
    assert item_b.user_id == user_b.id


# ---------------------------------------------------------------------------
# Reverse — deletes only this migration's copies; unrelated rows and the
# original PersonalEntry (this migration never deletes originals) survive.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_reverse_deletes_only_migrated_copies(make_user):
    user = make_user()
    entry = _make_goods(user, title="이전 대상")
    pre_existing = CollectionItem.objects.create(
        user=user, name="원래 있던 아이템", item_type="plush"
    )

    from django.apps import apps as real_apps

    module = _migration_module()
    module.migrate_goods_to_collection_items(real_apps, None)
    assert CollectionItem.objects.count() == 2

    module.delete_migrated_collection_items(real_apps, None)

    assert CollectionItem.objects.count() == 1
    assert CollectionItem.objects.filter(pk=pre_existing.pk).exists()
    # The original GOODS row itself is untouched — this migration never
    # deletes it (that is a separate, later migration's job).
    assert PersonalEntry.objects.filter(pk=entry.pk).exists()
