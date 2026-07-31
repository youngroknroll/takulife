"""드래프트 도메인의 공개 조회 계층. 집계 로직은 여기 두고 뷰에는 두지 않는다."""
from django.db.models import Count

from .models import DraftSource, EventDraft

_ALL_STATUSES = (
    EventDraft.ReviewStatus.PENDING,
    EventDraft.ReviewStatus.APPROVED,
    EventDraft.ReviewStatus.REJECTED,
)


def draft_review_stats() -> dict:
    """리뷰 상태별 개수를 pending/approved/rejected 키로 반환한다. 레코드가 0건이어도
    세 키 모두 채워진다."""
    rows = (
        EventDraft.objects.values("review_status")
        .annotate(count=Count("id"))
    )
    counts = {row["review_status"]: row["count"] for row in rows}
    return {status: counts.get(status, 0) for status in _ALL_STATUSES}


DRAFT_LISTING_PAGE_SIZE = 10


def list_drafts(status: str = ""):
    """review_status로 필터링할 수 있다(기본은 전체). 알 수 없는 status 값은 빈
    쿼리셋을 반환하며, 값 정규화는 뷰의 책임이다."""
    qs = EventDraft.objects.order_by("-id")
    if status:
        qs = qs.filter(review_status=status)
    return qs


def list_draft_sources():
    """enabled=True인 소스가 먼저 오고(실제로 수집 중인 것들), 그다음 이름순으로
    정렬한다."""
    return DraftSource.objects.order_by("-enabled", "name")


def enabled_draft_sources_exist() -> bool:
    """활성화된 소스가 하나도 없으면 discover_drafts를 굳이 실행하지 않기 위한 사전
    확인용이다 — DRAFT_DISCOVERY_ENABLED 꺼짐 상태와 마찬가지로 '할 일 없음'도 정상
    상태로 취급한다."""
    return DraftSource.objects.filter(enabled=True).exists()
