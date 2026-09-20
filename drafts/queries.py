"""드래프트 도메인의 공개 조회 계층. 집계 로직은 여기 두고 뷰에는 두지 않는다."""
from datetime import timedelta
from urllib.parse import urlsplit

from django.db.models import Avg, Case, Count, DurationField, ExpressionWrapper, F, Min, Q, When
from django.db.models.functions import Coalesce
from django.utils import timezone

from .discovery_runs import runner_is_online
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
    제외한다. 다만 손상되거나 알 수 없는 유형은 일부러 포함한다 — 여기서 거짓을
    돌리면 스태프 콘솔이 수집 명령을 아예 실행하지 않아 그 소스의 실패가 영영
    드러나지 않기 때문이다."""
    return (
        DraftSource.objects.filter(enabled=True)
        .exclude(source_type__in=DraftSource.ACCOUNT_SOURCE_TYPES)
        .exists()
    )


def runner_status():
    """단일 행(pk=1) DiscoveryRunnerStatus를 돌려주거나, 아직 heartbeat가 없으면
    None을 돌려준다."""
    return DiscoveryRunnerStatus.objects.filter(pk=1).first()


# phase별 한국어 라벨 — local_runner.progress의 PHASE_LABELS와 문자 그대로
# 일치해야 한다(S14 가드, 대시보드와 러너 터미널이 같은 어휘를 쓴다).
DISCOVERY_PHASE_LABELS = {
    DiscoveryRunnerStatus.Phase.IDLE: "대기",
    DiscoveryRunnerStatus.Phase.EXPLORING: "검색 중",
    DiscoveryRunnerStatus.Phase.READING: "행사 확인 중",
    DiscoveryRunnerStatus.Phase.SUBMITTING: "소스 후보 제출 중",
    DiscoveryRunnerStatus.Phase.COMPLETING: "완료 보고 정리 중",
}


def runner_live_summary():
    """대시보드 폴링이 쓰는 러너 실시간 상태 8키를 계산한다. 진행 행은
    온라인이고 idle이 아니고 상세 문구가 있을 때만 노출한다(D8)."""
    status = runner_status()
    online = runner_is_online(status_row=status)
    phase = status.phase if status else DiscoveryRunnerStatus.Phase.IDLE
    detail = status.phase_detail if status else ""
    active_statuses = [SourceDiscoveryRun.Status.PENDING, SourceDiscoveryRun.Status.CLAIMED]
    return {
        "online": online,
        "phase": phase,
        "phase_label": DISCOVERY_PHASE_LABELS.get(phase, "대기"),
        "detail": detail,
        "progress_visible": online and phase != DiscoveryRunnerStatus.Phase.IDLE and bool(detail),
        "current_run_id": status.current_run_id if status else None,
        "last_heartbeat_at": status.last_heartbeat_at if status else None,
        "active": SourceDiscoveryRun.objects.filter(status__in=active_statuses).exists(),
    }


# 사유별 한국어 라벨(허용 목록 EVENT_OUTCOME_REASONS 전 값을 덮어야 한다). 빈 값은
# created·duplicate 전용이라 화면에 그대로 빈 문자열로 낸다.
EVENT_OUTCOME_REASON_LABELS = {
    "": "",
    "known_url": "이미 등록된 URL",
    "agent_ended": "종료된 행사(탐색 판단)",
    "agent_overseas": "해외 행사(탐색 판단)",
    "host_blocked": "차단된 호스트",
    "blocked": "접근 차단",
    "fetch_empty": "빈 응답",
    "interpret_error": "해석 오류",
    "no_title": "제목 없음",
    "submit_error": "제출 오류",
    "fetch_error": "가져오기 오류",
    "not_event": "행사 아님",
    "overseas": "해외 행사",
    "ended": "종료된 행사",
    "server_overseas": "해외 행사(서버 판단)",
    "server_ended": "종료된 행사(서버 판단)",
}

# outcome별 (한국어 라벨, 배지 톤). 모르는 outcome은 아래에서 fallback 처리한다.
EVENT_OUTCOME_LABELS = {
    "created": ("생성됨", "ok"),
    "duplicate": ("중복", "disabled"),
    "excluded": ("제외", "disabled"),
    "skipped": ("건너뜀", "disabled"),
    "failed": ("실패", "error"),
}


def _display_url(url) -> str:
    """쿼리·프래그먼트를 뗀 호스트+경로만 남긴다(상세 표에 링크가 아닌 텍스트로 노출)."""
    parts = urlsplit(url)
    # netloc이 아니라 hostname — URL에 섞인 계정 정보(user:pass@)를 화면에 내지 않는다.
    return f"{parts.hostname or ''}{parts.path}"


def _outcome_rows(event_outcomes):
    """run.event_outcomes(이미 로딩된 JSON 필드)만 써서 표시용 행을 만든다 — 추가
    쿼리를 내지 않는다. 저장 전 검증되지만 형태가 틀어진 항목은 방어적으로 건너뛴다."""
    rows = []
    for item in event_outcomes:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if not isinstance(url, str):
            continue
        outcome = item.get("outcome", "")
        reason = item.get("reason", "")
        outcome_label, tone = EVENT_OUTCOME_LABELS.get(outcome, ("알 수 없음", "disabled"))
        rows.append(
            {
                "display_url": _display_url(url),
                "outcome": outcome,
                "outcome_label": outcome_label,
                "tone": tone,
                "reason_label": EVENT_OUTCOME_REASON_LABELS.get(reason, "알 수 없음"),
            }
        )
    return rows


def recent_discovery_runs(*, limit=5):
    """최근 탐색 실행을 최신순으로, 후보 승격/실패·행사 생성 개수와 표시용 결과
    행을 함께 계산해 dict 리스트로 돌려준다(뷰가 아니라 여기서 집계한다).

    후보·행사 드래프트를 같은 쿼리에서 Count하면 조인 곱으로 부풀어 distinct가
    필요하다. events_excluded·events_failed는 event_outcomes가 비어 있던 옛
    실행에서는 필드값을 믿을 수 없어 None으로 낸다(화면이 "-"로 표시)."""
    runs = SourceDiscoveryRun.objects.order_by("-created_at").annotate(
        promoted_count=Count(
            "candidates",
            filter=Q(candidates__status=SourceCandidate.Status.PROMOTED),
            distinct=True,
        ),
        failed_count=Count(
            "candidates",
            filter=Q(candidates__status=SourceCandidate.Status.FAILED),
            distinct=True,
        ),
        events_created=Count("events", distinct=True),
    )[:limit]
    rows = []
    for run in runs:
        has_outcomes = bool(run.event_outcomes)
        rows.append(
            {
                "run": run,
                "promoted_count": run.promoted_count,
                "failed_count": run.failed_count,
                "events_created": run.events_created,
                "events_excluded": run.events_excluded if has_outcomes else None,
                "events_failed": run.events_failed if has_outcomes else None,
                "outcome_rows": _outcome_rows(run.event_outcomes),
            }
        )
    return rows


def failed_source_candidates(*, limit=10):
    """최근 실패한 후보를 최신순으로 돌려준다(스태프 확인 큐)."""
    return SourceCandidate.objects.filter(
        status=SourceCandidate.Status.FAILED
    ).order_by("-created_at")[:limit]
