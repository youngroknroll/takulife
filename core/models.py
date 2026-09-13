"""core/models.py — 홈 화면 설정 모델.

싱글턴 HomeConfig가 스태프가 큐레이션한 카테고리 노출 설정을 저장한다.
비즈니스 규칙(대체값, 어휘 검증, 정렬)은 뷰가 아니라 여기 둔다.
"""
from django.db import models
from django.dispatch import Signal

from core.categories import PALETTE
from core.validators import validate_category_slug

# 카테고리가 활성→비활성으로 전이됐을 때만 보낸다. core는 events를 임포트할
# 수 없어(아키텍처 경계 R1) 반납에 필요한 게시 이벤트 수를 직접 셀 수
# 없다 — 그래서 core는 "무엇이 바뀌었는지"만 신호로 알리고, 실제 반납
# 판단(core.categories.reconcile_palette_slot 호출)은 이 신호를 구독하는
# events 쪽(events/signals.py)에서 한다.
category_deactivated = Signal()


class PaletteSlotsExhaustedError(Exception):
    """신규 카테고리 생성 시 빈 팔레트 슬롯이 없을 때만 던진다.

    반납 후 재획득(이후 단계) 실패는 이 예외가 아니라 palette_slot=None
    폴백으로 처리한다 — None이 유효한 이유는 "재획득 실패"이지
    "생성 실패"가 아니기 때문이다.
    """


class Category(models.Model):
    """카테고리 어휘 항목 하나(트랙 27 1단계).

    core.vocab.CATEGORY를 DB로 옮기는 첫 산물이며, 이 단계는 스키마만
    만든다 — core.vocab 조회 전환은 4단계다.

    palette_slot 배정: 신규 생성 시 빈 슬롯을 자동 배정하고, 슬롯이
    모두 찼으면 PaletteSlotsExhaustedError로 생성 자체를 막는다(관리
    화면이 잡아 안내할 예정). 슬롯 상한(PALETTE_SLOT_COUNT)은
    core.categories.PALETTE 길이에서 파생시켜 CSS 팔레트 토큰·계약
    테스트와 어긋나지 않게 한다.
    """

    PALETTE_SLOT_COUNT = len(PALETTE)

    slug = models.CharField(
        max_length=64, unique=True, validators=[validate_category_slug]
    )
    # 라벨 유일성은 같은 칩에 서로 다른 카테고리가 합쳐지는 결함을 막는 제약이다.
    label = models.CharField(max_length=64, unique=True)
    is_active = models.BooleanField(default=True)
    # null=True: "미배정"은 정상 상태(재획득 실패 폴백). unique=True로 두 카테고리가
    # 같은 색을 갖는 경합을 DB 레벨에서도 막는다(NULL은 유일성 검사에서 제외됨).
    palette_slot = models.PositiveSmallIntegerField(null=True, blank=True, unique=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # 저장 시점에 활성→비활성 전이를 알아채기 위한 로드 시점 스냅샷.
        # save()마다 DB를 다시 읽는 대신(추가 쿼리) 인메모리로 비교한다.
        self._initial_is_active = self.is_active

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        if is_new and self.palette_slot is None:
            self.palette_slot = self._next_available_slot()

        became_inactive = (
            not is_new and self._initial_is_active and not self.is_active
        )

        super().save(*args, **kwargs)
        self._initial_is_active = self.is_active

        if became_inactive:
            category_deactivated.send(sender=Category, category=self)

    @classmethod
    def _next_available_slot(cls):
        # 동시 요청 경합의 최종 방어선은 palette_slot의 DB 유일 제약이다.
        # 재시도나 select_for_update 같은 명시적 잠금은 이 모델을 호출하는
        # 서비스 계층(트랙 27 11단계)에서 필요할 때 추가한다.
        used_slots = set(
            cls.objects.exclude(palette_slot=None).values_list(
                "palette_slot", flat=True
            )
        )
        for slot in range(cls.PALETTE_SLOT_COUNT):
            if slot not in used_slots:
                return slot
        raise PaletteSlotsExhaustedError("사용 가능한 팔레트 슬롯이 없습니다.")


class HomeConfig(models.Model):
    """홈 화면 카테고리 노출을 위한 싱글턴 설정.

    featured_categories: 스태프가 선택한 카테고리 슬러그의 순서 있는 목록.
    빈 리스트면 어휘 순서대로 모든 카테고리를 보여준다(하위 호환 대체값).
    """

    featured_categories = models.JSONField(default=list)

    class Meta:
        verbose_name = "Home page configuration"

    @classmethod
    def get_solo(cls):
        """싱글턴 인스턴스(pk=1)를 반환한다. 없으면 생성한다."""
        instance, _ = cls.objects.get_or_create(pk=1)
        return instance

    def featured_category_pairs(self):
        """노출 카테고리의 (slug, label) 쌍을 반환한다.

        core.vocab 상수 대신 DB(Category)를 조회한다 — 다음 단계에서
        core.vocab이 Category를 읽게 되므로, 여기서 core.vocab을 계속
        참조하면 vocab↔models 순환 임포트가 생기기 때문이다.

        - featured_categories가 비어 있으면 활성 카테고리 전체를
          sort_order 순으로 반환(대체값).
        - 비어 있지 않으면 저장된 순서대로 반환하되, DB에 없는 슬러그는
          조용히 제외하고(검증 가드), 비활성 카테고리도 제외한다 — 이
          목록은 소비자 필터가 아니라 스태프가 고른 홈 큐레이션 타일이라
          스태프가 비활성화한 카테고리를 계속 노출할 이유가 없다.
        """
        if not self.featured_categories:
            return list(
                Category.objects.filter(is_active=True).values_list(
                    "slug", "label"
                )
            )

        categories_by_slug = {
            category.slug: category
            for category in Category.objects.filter(
                slug__in=self.featured_categories, is_active=True
            )
        }
        return [
            (slug, categories_by_slug[slug].label)
            for slug in self.featured_categories
            if slug in categories_by_slug
        ]


class AnalyticsEvent(models.Model):
    """기록된 행동 분석 이벤트 하나.

    새 앱이 아니라 core(모든 도메인이 이미 의존하는 공용 앱)에 둔다 —
    기록은 도메인을 가로지르는 관심사(events, archive)이고 core가 그
    공유 지점이기 때문이다.

    프라이버시: 사용자는 가명이며 복원 불가능한 ``user_key``로만
    저장하고(core.analytics.pseudonymous_user_key 참고), 사용자를 직접
    가리키는 FK는 두지 않는다 — 이 테이블은 accounts.User로 조인해
    되돌아갈 수 없도록 의도적으로 설계됐다. ``context``에는 자유
    텍스트, 연락처, 미디어 URL이 절대 들어가면 안 되며(이 모델이 아니라
    core.analytics.record_event의 금지 키 가드가 강제한다).
    """

    class EventName(models.TextChoices):
        EVENT_LIST_VIEWED = "event_list_viewed", "Event list viewed"
        EVENT_SEARCHED = "event_searched", "Event searched"
        EVENT_DETAIL_VIEWED = "event_detail_viewed", "Event detail viewed"
        EVENT_INTERESTED = "event_interested", "Event interested"
        EVENT_PLANNED = "event_planned", "Event planned"
        EVENT_MARKED_VISITED = "event_marked_visited", "Event marked visited"
        VISIT_RECORD_CREATED = "visit_record_created", "Visit record created"
        VISIT_PHOTO_ADDED = "visit_photo_added", "Visit photo added"
        COLLECTION_ITEM_CREATED = "collection_item_created", "Collection item created"
        COLLECTION_ITEM_UPDATED = "collection_item_updated", "Collection item updated"
        COLLECTION_ITEM_LINKED_TO_VISIT = (
            "collection_item_linked_to_visit",
            "Collection item linked to visit",
        )
        COLLECTION_ITEM_MARKED_WANTED = (
            "collection_item_marked_wanted",
            "Collection item marked wanted",
        )
        COLLECTION_ITEM_MARKED_TRADEABLE = (
            "collection_item_marked_tradeable",
            "Collection item marked tradeable",
        )

    event_name = models.CharField(max_length=32, choices=EventName.choices)
    # 가명 사용자별 코호트 키(core.analytics 참고). 익명/미인증 요청은 "".
    # 사용자를 직접 가리키지 않는다.
    user_key = models.CharField(max_length=64, blank=True)
    # 이벤트에 단일 대상이 없으면(예: 목록 조회) "".
    target_type = models.CharField(max_length=32, blank=True)
    target_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    context = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["event_name", "created_at"]),
        ]
