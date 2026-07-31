"""GOODS PersonalEntry -> CollectionItem 데이터 마이그레이션 테스트
(컬렉션 도메인 설계 계획 §3-5, PR-C4 stage C).

RunPython 데이터 마이그레이션 테스트는 CP10 선례(test_visit_record_status_
orchestration.py)를 따른다: 마이그레이션 모듈을 임포트해 그 함수를 고정된
과거 레지스트리가 아니라 ``django.apps.apps`` 대상으로 직접 호출함으로써,
``manage.py migrate`` 가 실행할 것과 동일한 함수를 검증한다.

테스트 행은 일부러 ``PersonalEntry.Kind.GOODS`` 대신 리터럴 문자열 "goods"로
만든다 — 이 enum 멤버는 같은 트랙의 이후 커밋(§3-5 M2)에서 제거되므로, 그때
이 파일을 고칠 필요가 없게 하기 위함이다.
"""
import importlib

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from archive.models import CollectionItem, EventInterest, PersonalEntry, UserEventStatus, VisitRecord

pytestmark = pytest.mark.contract


def _migration_module():
    return importlib.import_module(
        "archive.migrations.0017_migrate_goods_to_collection_items"
    )


def _make_goods(user, **kwargs):
    kwargs.setdefault("title", "굿즈 항목")
    return PersonalEntry.objects.create(user=user, kind="goods", **kwargs)


# ---------------------------------------------------------------------------
# 필드 매핑
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_GOODS_항목을_이관하면_기본_필드와_분류_라벨이_컬렉션_아이템에_반영된다(make_user):
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
def test_분류가_슬러그와_일치하면_그대로_굿즈_종류로_매핑된다(make_user):
    user = make_user()
    _make_goods(user, category="badge")

    from django.apps import apps as real_apps

    _migration_module().migrate_goods_to_collection_items(real_apps, None)

    item = CollectionItem.objects.get(user=user)
    assert item.item_type == "badge"


@pytest.mark.django_db
def test_분류가_일치하지_않으면_굿즈_종류가_기타로_매핑된다(make_user):
    user = make_user()
    _make_goods(user, category="완전히 다른 분류")

    from django.apps import apps as real_apps

    _migration_module().migrate_goods_to_collection_items(real_apps, None)

    item = CollectionItem.objects.get(user=user)
    assert item.item_type == "etc"


@pytest.mark.django_db
def test_분류가_비어있으면_굿즈_종류가_기타로_매핑된다(make_user):
    user = make_user()
    _make_goods(user, category="")

    from django.apps import apps as real_apps

    _migration_module().migrate_goods_to_collection_items(real_apps, None)

    item = CollectionItem.objects.get(user=user)
    assert item.item_type == "etc"


# ---------------------------------------------------------------------------
# 방어적 실패 — 전체 실행을 중단하고 부분 커밋을 허용하지 않는다
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_방문_기록이_참조하는_굿즈가_있으면_전체_이관이_중단된다(make_user):
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
    # 전부 아니면 전무: 그 자체로 유효한 "clean" 행도 이관되면 안 된다.
    assert CollectionItem.objects.count() == 0
    assert clean.id is not None  # 확인용: clean 행은 그대로 존재함


@pytest.mark.django_db
def test_찜_기록이_참조하는_굿즈가_있으면_전체_이관이_중단된다(make_user):
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
def test_사용자_행사_상태가_참조하는_굿즈가_있으면_전체_이관이_중단된다(make_user):
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
def test_URL이_채워진_굿즈가_있으면_전체_이관이_중단된다(make_user):
    user = make_user()
    blocked = _make_goods(user, url="https://example.com/goods")

    from django.apps import apps as real_apps

    with pytest.raises(Exception) as exc_info:
        _migration_module().migrate_goods_to_collection_items(real_apps, None)

    assert f"PersonalEntry(id={blocked.id})" in str(exc_info.value)
    assert CollectionItem.objects.count() == 0


@pytest.mark.django_db
def test_지역이_채워진_굿즈가_있으면_전체_이관이_중단된다(make_user):
    user = make_user()
    blocked = _make_goods(user, region="seoul")

    from django.apps import apps as real_apps

    with pytest.raises(Exception) as exc_info:
        _migration_module().migrate_goods_to_collection_items(real_apps, None)

    assert f"PersonalEntry(id={blocked.id})" in str(exc_info.value)
    assert CollectionItem.objects.count() == 0


@pytest.mark.django_db
def test_공식_등록_검토가_제출된_굿즈가_있으면_전체_이관이_중단된다(make_user):
    user = make_user()
    blocked = _make_goods(user, promotion_status="submitted")

    from django.apps import apps as real_apps

    with pytest.raises(Exception) as exc_info:
        _migration_module().migrate_goods_to_collection_items(real_apps, None)

    assert f"PersonalEntry(id={blocked.id})" in str(exc_info.value)
    assert CollectionItem.objects.count() == 0


# ---------------------------------------------------------------------------
# CP-Image — 이관된 CollectionItem은 물리적으로 독립된 파일을 갖는다. 그래야
# PersonalEntry의 post_delete 스토리지 정리(archive/signals.py)가 이관된
# 사본을 조용히 지워버리는 일이 없다.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_이미지가_있는_굿즈를_이관하면_원본과_물리적으로_독립된_파일이_생성된다(
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

    # (1) 원본과 다른 저장 키 — 물리적으로 같은 파일을 절대 공유하지 않는다.
    assert item.image.name != original_name

    # (2)+(3) 실제(과거 이력이 아닌) 행을 삭제해 PersonalEntry의 post_delete
    # 시그널을 실제로 발생시키고, 원본 파일이 사라졌는지로 시그널이 정말
    # 실행됐음을 증명한다.
    real_entry = PersonalEntry.objects.get(pk=entry.pk)
    with django_capture_on_commit_callbacks(execute=True):
        real_entry.delete()
    assert storage.exists(original_name) is False

    # (4) 이관된 사본은 원본 행이 삭제돼도 영향받지 않고 남는다.
    item.refresh_from_db()
    assert storage.exists(item.image.name) is True


@pytest.mark.django_db
def test_이미지가_없는_굿즈도_오류_없이_이관된다(make_user):
    user = make_user()
    _make_goods(user)

    from django.apps import apps as real_apps

    _migration_module().migrate_goods_to_collection_items(real_apps, None)

    item = CollectionItem.objects.get(user=user)
    assert not item.image


# ---------------------------------------------------------------------------
# 여러 사용자 / 여러 행에 대한 처리 검증
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_여러_사용자의_굿즈를_이관하면_각자_소유로_분리된_컬렉션_아이템이_생긴다(make_user):
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
# 역방향 — 이 마이그레이션이 만든 사본만 삭제한다. 관련 없는 행과 원본
# PersonalEntry(이 마이그레이션은 원본을 삭제하지 않음)는 그대로 남는다.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_역방향_마이그레이션은_이관된_사본만_삭제하고_원본과_기존_항목은_보존한다(make_user):
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
    # 원본 GOODS 행 자체는 그대로다 — 이 마이그레이션은 이를 삭제하지 않는다
    # (그것은 별도의 이후 마이그레이션이 할 일이다).
    assert PersonalEntry.objects.filter(pk=entry.pk).exists()
