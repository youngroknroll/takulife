"""Category.palette_slot 반납·재획득 생명주기 — 트랙 27 6단계 Phase A.

Browser Interaction Reviewer가 최초 규칙("게시 이벤트 0건이면 슬롯 반납")의
Critical 결함을 잡았다: 새로 만든 카테고리는 정의상 게시 이벤트가 0건이라
생성 직후 자기 슬롯을 반납해 버렸다. 확정된 규칙(CLAUDE.md 트랙 27 6단계
배경, 사용자 결정 2026-09-12~13)은 활성 여부를 함께 봐야 한다:

- 활성 + 게시 이벤트 0건 → 슬롯 유지
- 비활성 + 게시 이벤트 0건 → 슬롯 반납
- 비활성이어도 게시 이벤트가 남아 있으면 → 슬롯 유지
- 반납 후 재게시 → 빈 슬롯 있으면 재획득, 없으면 None 유지(게시는 막지 않음)
- 반납·재획득 재계산은 게시상태 전이 시점에만. 조회(GET) 시점 재계산 금지

⚠️ 반납·재획득 로직은 2026-09-13 기준 core/models.py, events/services.py
어디에도 없다([코드] — Category.save()는 생성 시 자동 배정만 하고,
core/categories.py의 category_exists/category_label은 순수 조회만 하며,
events/services.py의 unpublish_event/republish_event는 palette_slot을
전혀 건드리지 않는다). 그래서 이 파일의 테스트 중 실제 상태 전이(반납·
재획득)를 요구하는 것들은 지금 Red고, "슬롯이 그대로 유지된다"만
단언하는 것들은 반납 로직 자체가 없어 지금은 공허하게 참(Green)이다 —
이후 반납·재획득이 구현된 뒤에도 깨지지 않아야 하는 회귀 핀으로 남긴다.
자세한 판단은 보고 참고.

⚠️ 반납·재획득 트리거 위치(Category.save()인지, events.services의 전이
함수들인지, 둘 다인지)는 아직 정해지지 않았다. 그래서 여기 테스트는
카테고리 필드를 직접 조작해 반납 상태를 만들지 않고, 실제 게시상태 전이
함수(events.services.create_published_event/unpublish_event/
republish_event)를 거쳐 상태를 만든다 — "이벤트를 비공개로 돌리면
결과적으로 슬롯이 반납된다"까지만 단언하고 어느 함수가 그렇게 했는지는
묻지 않는다.
"""
import pytest

from core.categories import category_exists, category_label
from core.models import Category
from events.models import Event
from events.services import create_published_event, republish_event, unpublish_event

pytestmark = [pytest.mark.django_db, pytest.mark.domain]


def _create_category(*, slug, label, is_active=True):
    return Category.objects.create(slug=slug, label=label, is_active=is_active)


def _create_published_event(*, category_slug, official_url):
    return create_published_event(
        title=f"이벤트_{category_slug}",
        category=category_slug,
        official_url=official_url,
    )


def _published_count(*, category_slug):
    return Event.objects.filter(
        category=category_slug, publish_status=Event.PublishStatus.PUBLISHED
    ).count()


def test_방금_만든_활성_카테고리는_게시_이벤트가_0건이어도_슬롯을_유지한다():
    category = _create_category(slug="lifecycle_p01", label="P01라벨")
    assigned_slot = category.palette_slot
    assert assigned_slot is not None
    assert _published_count(category_slug=category.slug) == 0

    # 조회(읽기)만 여러 번 수행한다 — 반납 재계산이 읽기 경로에 잘못
    # 끼어들면 여기서 깨진다(BIR Critical 회귀 핀).
    category_label(category.slug)
    category_exists(category.slug)

    category.refresh_from_db()
    assert category.palette_slot == assigned_slot


def test_비활성이고_게시_이벤트가_0건이면_슬롯을_반납한다():
    category = _create_category(slug="lifecycle_p02", label="P02라벨")
    event = _create_published_event(
        category_slug=category.slug, official_url="https://example.com/p02"
    )

    category.is_active = False
    category.save()

    unpublish_event(event=event)  # 게시상태 전이 — 반납 재계산 시점

    category.refresh_from_db()
    assert category.palette_slot is None


def test_비활성이어도_게시_이벤트가_남아_있으면_슬롯을_유지한다():
    category = _create_category(slug="lifecycle_p03", label="P03라벨")
    assigned_slot = category.palette_slot
    event_a = _create_published_event(
        category_slug=category.slug, official_url="https://example.com/p03-a"
    )
    _create_published_event(
        category_slug=category.slug, official_url="https://example.com/p03-b"
    )

    category.is_active = False
    category.save()

    unpublish_event(event=event_a)  # 남은 event_b가 여전히 게시 중 → 게시 건수 1

    category.refresh_from_db()
    assert category.palette_slot == assigned_slot


def test_활성_카테고리는_게시_이벤트가_0건이_되어도_슬롯을_유지한다():
    category = _create_category(slug="lifecycle_p04", label="P04라벨")
    assigned_slot = category.palette_slot
    event = _create_published_event(
        category_slug=category.slug, official_url="https://example.com/p04"
    )

    unpublish_event(event=event)  # 활성 상태 그대로, 게시 건수만 0으로

    category.refresh_from_db()
    assert category.palette_slot == assigned_slot


def test_반납된_슬롯은_새_카테고리가_재사용할_수_있다():
    category = _create_category(slug="lifecycle_p05", label="P05라벨")
    freed_slot = category.palette_slot
    event = _create_published_event(
        category_slug=category.slug, official_url="https://example.com/p05"
    )

    category.is_active = False
    category.save()
    unpublish_event(event=event)

    category.refresh_from_db()
    assert category.palette_slot is None  # 사전조건: 반납됐어야 한다

    new_category = _create_category(slug="lifecycle_p05_new", label="P05새라벨")
    assert new_category.palette_slot == freed_slot


def test_슬롯을_반납한_카테고리의_이벤트가_재게시되면_빈_슬롯을_다시_받는다():
    category = _create_category(slug="lifecycle_p06", label="P06라벨")
    event = _create_published_event(
        category_slug=category.slug, official_url="https://example.com/p06"
    )

    category.is_active = False
    category.save()
    unpublish_event(event=event)

    category.refresh_from_db()
    assert category.palette_slot is None  # 사전조건: 반납됐어야 한다

    republish_event(event=event)  # 게시상태 전이 — 재획득 시점

    category.refresh_from_db()
    assert category.palette_slot is not None


def test_빈_슬롯이_없으면_재획득에_실패해도_게시를_막지_않는다():
    category = _create_category(slug="lifecycle_p07", label="P07라벨")
    event = _create_published_event(
        category_slug=category.slug, official_url="https://example.com/p07"
    )

    category.is_active = False
    category.save()
    unpublish_event(event=event)

    category.refresh_from_db()
    assert category.palette_slot is None  # 사전조건: 반납됐어야 한다

    # 남은 빈 슬롯을 전부 다른 카테고리로 채운다. 슬롯 총량·현재 점유
    # 수에서 빈 슬롯 수를 파생시킨다 — 하드코딩 금지.
    occupied = Category.objects.exclude(palette_slot=None).count()
    free_count = Category.PALETTE_SLOT_COUNT - occupied
    for index in range(free_count):
        _create_category(slug=f"lifecycle_p07_fill_{index}", label=f"P07채움{index}")

    assert (
        Category.objects.exclude(palette_slot=None).count()
        == Category.PALETTE_SLOT_COUNT
    )

    republished_event = republish_event(event=event)  # 재획득 시도 — 빈 슬롯 없음

    assert republished_event.publish_status == Event.PublishStatus.PUBLISHED
    category.refresh_from_db()
    assert category.palette_slot is None  # 재획득 실패해도 게시는 막지 않는다


def test_한_번도_쓰이지_않은_카테고리를_비활성화하면_슬롯이_즉시_반납된다():
    # 이벤트를 한 번도 만들지 않아 게시상태 전이가 영영 일어나지 않는
    # 카테고리다. 반납 트리거를 이벤트 전이에만 두면 이런 카테고리의
    # 슬롯은 영구히 잠긴다 — 그래서 카테고리 활성 상태 전이(True→False)
    # 자체도 반납 트리거여야 한다.
    category = _create_category(slug="lifecycle_p09", label="P09라벨")
    freed_slot = category.palette_slot
    assert freed_slot is not None

    category.is_active = False
    category.save()

    category.refresh_from_db()
    assert category.palette_slot is None

    new_category = _create_category(slug="lifecycle_p09_new", label="P09새라벨")
    assert new_category.palette_slot == freed_slot


def test_목록을_여러_번_조회해도_슬롯_배정이_바뀌지_않는다():
    # 이벤트 전이를 한 번도 거치지 않은 채로 "반납 조건"(비활성 + 게시
    # 이벤트 0건)을 이미 만족하는 상태를 만든다. 게시상태 전이가 없었으니
    # 반납이 실제로 일어났는지와 무관하게, 조회만으로는 슬롯이 절대
    # 바뀌면 안 된다(BIR 수용 기준 1: 조회 시점 재계산 금지).
    category = _create_category(slug="lifecycle_p08", label="P08라벨", is_active=False)
    assigned_slot = category.palette_slot
    assert assigned_slot is not None
    assert _published_count(category_slug=category.slug) == 0

    for _ in range(3):
        category_label(category.slug)
        category_exists(category.slug)

    category.refresh_from_db()
    assert category.palette_slot == assigned_slot
