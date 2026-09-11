"""드래프트 도메인의 공개 조회 계층. 집계 로직은 여기 두고 뷰에는 두지 않는다."""
from datetime import timedelta

from django.db.models import Avg, Case, Count, DurationField, ExpressionWrapper, F, Min, Q, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from .models import (
    DiscoveryRunnerStatus,
    DraftSource,
    EventDraft,
    SourceCandidate,
    SourceDiscoveryRun,
)

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


def draft_review_sla(*, days=7, now=None) -> dict:
    """검수 SLA 세 값을 돌려준다. 기산점은 재오픈 시각이 있으면 그 값, 없으면 생성 시각이다.
    결정 시각이 없는 옛 승인·반려 건은 창 안에 못 들어오므로 자동으로 빠진다."""
    now = now or timezone.now()
    window_start = now - timedelta(days=days)
    started_at = Coalesce("reopened_at", "created_at")
    pending = EventDraft.objects.filter(review_status=EventDraft.ReviewStatus.PENDING).aggregate(
        oldest=Min(started_at), count=Count("id"))
    decided = (
        EventDraft.objects.annotate(
            started_at=started_at,
            decided_at=Case(
                When(review_status=EventDraft.ReviewStatus.APPROVED, then=F("approved_at")),
                When(review_status=EventDraft.ReviewStatus.REJECTED, then=F("rejected_at")),
            ),
        )
        .filter(decided_at__gte=window_start, decided_at__lt=now)
        .aggregate(
            avg_handling=Avg(ExpressionWrapper(F("decided_at") - F("started_at"), output_field=DurationField())),
            count=Count("id"),
            rejected=Count("id", filter=Q(review_status=EventDraft.ReviewStatus.REJECTED)),
        )
    )
    decided_count = decided["count"]
    return {
        "longest_wait": (now - pending["oldest"]) if pending["oldest"] else None,
        "avg_handling": decided["avg_handling"],
        "rejection_rate": (decided["rejected"] / decided_count) if decided_count else None,
        "pending_count": pending["count"],
        "decided_count": decided_count,
        "rejected_count": decided["rejected"],
    }


DRAFT_LISTING_PAGE_SIZE = 14


def list_drafts(status: str = "", search: str = ""):
    """review_status로 필터링할 수 있다(기본은 전체). 알 수 없는 status 값은 빈
    쿼리셋을 반환하며, 값 정규화는 뷰의 책임이다.

    search는 제목과 출처를 함께 본다 — 검수자가 기억하는 단서가 둘 중 어느
    쪽인지 미리 알 수 없다. extracted_title이 비어 있는 드래프트는 화면이
    raw_title을 대신 보여주므로 그쪽도 대상에 넣는다.
    """
    qs = EventDraft.objects.order_by("-id")
    if status:
        qs = qs.filter(review_status=status)
    term = search.strip()
    if term:
        qs = qs.filter(
            Q(extracted_title__icontains=term)
            | Q(raw_title__icontains=term)
            | Q(source_name__icontains=term)
            | Q(source_url__icontains=term)
        )
    return qs


def list_draft_sources():
    """enabled=True인 소스가 먼저 오고(실제로 수집 중인 것들), 그다음 이름순으로
    정렬한다."""
    return DraftSource.objects.order_by("-enabled", "name")


def enabled_draft_sources_exist() -> bool:
    """활성화된 소스가 하나도 없으면 discover_drafts를 굳이 실행하지 않기 위한 사전
    확인용이다 — DRAFT_DISCOVERY_ENABLED 꺼짐 상태와 마찬가지로 '할 일 없음'도 정상
    상태로 취급한다. 계정형 소스는 서버가 아닌 개인 맥 러너가 읽으므로 존재 여부에서
    제외한다."""
    return DraftSource.objects.filter(
        enabled=True,
        source_type__in=DraftSource.SERVER_COLLECTED_SOURCE_TYPES,
    ).exists()


def runner_status():
    """단일 행(pk=1) DiscoveryRunnerStatus를 돌려주거나, 아직 heartbeat가 없으면
    None을 돌려준다."""
    return DiscoveryRunnerStatus.objects.filter(pk=1).first()


def recent_discovery_runs(*, limit=5):
    """최근 탐색 실행을 최신순으로, 후보 승격/실패 개수를 함께 annotate해
    행 dict 리스트로 돌려준다(뷰가 아니라 여기서 집계한다)."""
    runs = SourceDiscoveryRun.objects.order_by("-created_at").annotate(
        promoted_count=Count(
            "candidates", filter=Q(candidates__status=SourceCandidate.Status.PROMOTED)
        ),
        failed_count=Count(
            "candidates", filter=Q(candidates__status=SourceCandidate.Status.FAILED)
        ),
    )[:limit]
    return [
        {"run": run, "promoted_count": run.promoted_count, "failed_count": run.failed_count}
        for run in runs
    ]


def failed_source_candidates(*, limit=10):
    """최근 실패한 후보를 최신순으로 돌려준다(스태프 확인 큐)."""
    return SourceCandidate.objects.filter(
        status=SourceCandidate.Status.FAILED
    ).order_by("-created_at")[:limit]
