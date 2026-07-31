"""core/models.py — 홈 화면 설정 모델.

싱글턴 HomeConfig가 스태프가 큐레이션한 카테고리 노출 설정을 저장한다.
비즈니스 규칙(대체값, 어휘 검증, 정렬)은 뷰가 아니라 여기 둔다.
"""
from django.db import models

from core.vocab import CATEGORY, CATEGORY_LABELS


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

        - featured_categories가 비어 있으면 어휘 순서대로 전체 CATEGORY를 반환(대체값).
        - 비어 있지 않으면 저장된 순서대로 반환하되, 어휘에 없는 슬러그는
          조용히 제외한다(검증 가드).
        """
        if not self.featured_categories:
            return list(CATEGORY)

        valid_slugs = set(CATEGORY_LABELS.keys())
        return [
            (slug, CATEGORY_LABELS[slug])
            for slug in self.featured_categories
            if slug in valid_slugs
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
