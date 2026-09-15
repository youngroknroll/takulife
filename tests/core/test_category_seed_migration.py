"""core/migrations/0006_seed_categories 시딩 마이그레이션 계약(트랙 27 3단계).

이 마이그레이션은 core.vocab.CATEGORY를 라이브 import하지 않고 그 시점의
동결 스냅샷을 심는다(마이그레이션 파일 상단 주석 참고, archive/0017 선례).
즉 core.vocab.CATEGORY가 나중에(트랙 27 4단계 포함) 바뀌어도 이미 적용된
0006은 여전히 옛 어휘를 심는 것이 맞는 동작이다 — 그래서 이 테스트의 핀도
core.vocab.CATEGORY를 라이브로 읽지 않고, 마이그레이션이 심어야 할 값을
독립적으로 하드코딩한다. 이렇게 해야 core.vocab이 나중에 바뀌어도 이 옛
마이그레이션의 계약이 거짓으로 깨지지 않으면서, 마이그레이션의 슬롯 배정
로직 자체가 어긋나면(예: 인덱스와 슬롯이 안 맞음) 여전히 실패한다.

선례는 tests/auth/test_nickname_backfill_migration.py의 MigrationExecutor
패턴을 그대로 따른다.
"""
import pytest
from django.core.management import call_command
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from core.categories import PALETTE

pytestmark = pytest.mark.contract


@pytest.fixture(autouse=True)
def _restore_migrations_to_head():
    """core를 0006 이전으로 되감으면 Django가 의존 관계상 staff.0011도 같이
    되감는다. 이 테스트는 core만 0006으로 다시 올리므로 staff는 head보다
    한 단계 뒤에 남아, 뒤이어 도는 다른 테스트가 없는 컬럼을 만난다. 매 테스트
    뒤에 전체 앱을 최신으로 다시 이주시켜 이 잔여 상태를 지운다."""
    yield
    call_command("migrate", verbosity=0)

# core/migrations/0006_seed_categories.py의 _CATEGORY와 같은 값(2026-09-13
# 기준)을 독립적으로 하드코딩한다 — core.vocab.CATEGORY를 참조하지 않는다.
# 마이그레이션은 적용된 과거의 고정 사실이므로, 어휘가 나중에 바뀌어도 이
# 목록은 바뀌지 않아야 한다.
_EXPECTED_SEEDED_CATEGORY = (
    ("popup_store", "팝업스토어"),
    ("collaboration_cafe", "콜라보 카페"),
    ("theater_bonus", "극장 특전"),
    ("goods_reservation", "굿즈 예약"),
    ("exhibition", "전시"),
    ("fan_meeting", "팬미팅"),
    ("concert", "콘서트"),
)


def _migrate_to(target):
    executor = MigrationExecutor(connection)
    executor.migrate(target)
    return executor.loader.project_state(target).apps


@pytest.mark.django_db(transaction=True)
def test_시딩_마이그레이션_적용_후_기존_카테고리가_모두_존재한다():
    _migrate_to([("core", "0005_category")])

    new_apps = _migrate_to([("core", "0006_seed_categories")])
    Category = new_apps.get_model("core", "Category")

    expected_slugs = {slug for slug, _ in _EXPECTED_SEEDED_CATEGORY}
    seeded_slugs = set(Category.objects.values_list("slug", flat=True))

    assert seeded_slugs == expected_slugs
    assert Category.objects.count() == len(_EXPECTED_SEEDED_CATEGORY)


@pytest.mark.django_db(transaction=True)
def test_시딩된_카테고리의_팔레트_슬롯이_서로_겹치지_않는다():
    _migrate_to([("core", "0005_category")])

    new_apps = _migrate_to([("core", "0006_seed_categories")])
    Category = new_apps.get_model("core", "Category")

    slots = list(Category.objects.values_list("palette_slot", flat=True))

    assert len(slots) == len(set(slots))
    assert all(0 <= slot < len(PALETTE) for slot in slots)


@pytest.mark.django_db(transaction=True)
def test_시딩된_슬롯이_기존_색_순서와_맞는다():
    _migrate_to([("core", "0005_category")])

    new_apps = _migrate_to([("core", "0006_seed_categories")])
    Category = new_apps.get_model("core", "Category")

    for index, (slug, _label) in enumerate(_EXPECTED_SEEDED_CATEGORY):
        category = Category.objects.get(slug=slug)
        assert category.palette_slot == index
