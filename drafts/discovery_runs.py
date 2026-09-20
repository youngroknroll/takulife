"""탐색 실행(run)·러너 heartbeat·임대 수명주기를 소유하는 서비스 계층."""
import logging
import uuid
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.crypto import constant_time_compare

from drafts.models import DiscoveryRunnerStatus, SourceCandidate, SourceDiscoveryRun

logger = logging.getLogger(__name__)

# 러너 폴링 주기에 여유를 둔 신선도 기준(초).
HEARTBEAT_FRESH_SECONDS = 120

# 에이전트 최악 실행(600초×2) + 첫 제출 검증까지 덮는 값. 이후 제출은 매번
# renew_lease로 갱신되므로 이 값은 최초 에이전트 국면 기준이다.
LEASE_SECONDS = 1800

# 최초 1회 + 재시도 1회까지만 재임대(정본 재시도 상한 결정).
MAX_LEASES = 2

# 러너가 보낸 원문 사유를 그대로 노출하지 않기 위한 허용 목록(보안 계약).
_ALLOWED_FAILURE_KINDS = {
    "agent_error",
    "agent_timeout",
    "invalid_output",
    "exploration_error",
    "runner_shutdown",
}

# 러너가 보내는 행사별 결과 outcome→허용 reason 집합(보안 계약, local_runner와
# 일치해야 한다 — local_runner.exploration_flow가 실제로 내는 값과 대조).
EVENT_OUTCOME_REASONS = {
    "skipped": {"known_url", "agent_ended", "agent_overseas"},
    "failed": {
        "host_blocked",
        "blocked",
        "fetch_empty",
        "interpret_error",
        "no_title",
        "submit_error",
        "fetch_error",
    },
    "excluded": {"not_event", "overseas", "ended", "server_overseas", "server_ended"},
    "created": {""},
    "duplicate": {""},
}

# drafts.agent_drafts.MAX_EVENTS_PER_RUN과 같은 값이다.
_MAX_EVENT_OUTCOMES = 20


def _clean_event_outcomes(raw, *, known_created_urls):
    """dict가 아니거나 허용목록 밖인 항목은 버리고 {url, outcome, reason}만
    남긴다 — 러너 원문을 그대로 믿지 않는다."""
    # candidate_validation·agent_drafts가 이 모듈을 임포트하므로 모듈
    # 최상단에서 그 반대 방향을 두면 순환 임포트가 된다 — 함수 안에서만 쓴다.
    from drafts.agent_drafts import _strip_tracking_params
    from drafts.candidate_validation import sanitize_text

    if not isinstance(raw, list):
        return []

    cleaned = []
    dropped = 0
    for item in raw:
        if not isinstance(item, dict):
            dropped += 1
            continue

        url = item.get("url")
        outcome = item.get("outcome")
        reason = item.get("reason")
        if not isinstance(url, str) or not isinstance(reason, str):
            dropped += 1
            continue

        url = sanitize_text(value=url)
        scheme = url.split("://", 1)[0] if "://" in url else ""
        if scheme not in ("http", "https") or len(url) > 200:
            dropped += 1
            continue

        allowed_reasons = EVENT_OUTCOME_REASONS.get(outcome)
        if allowed_reasons is None or reason not in allowed_reasons:
            dropped += 1
            continue

        # created는 실행이 실제로 만든 드래프트와 대조한다 — duplicate는
        # 다른 실행에서 먼저 만들어졌을 수 있어 대조하지 않는다.
        if outcome == "created" and _strip_tracking_params(url) not in known_created_urls:
            dropped += 1
            continue

        cleaned.append({"url": url, "outcome": outcome, "reason": reason})

    if dropped:
        logger.warning("dropped invalid event outcomes: count=%s", dropped)

    return cleaned[:_MAX_EVENT_OUTCOMES]


class RunnerOfflineError(Exception):
    pass


class DiscoveryRunActiveError(Exception):
    pass


class LeaseInvalidError(Exception):
    pass


def _classify_candidate_outcome(candidate_statuses):
    """소스 후보 상태 목록을 없음/정상/실패/부분 중 하나로 분류한다."""
    if not candidate_statuses:
        return "none"
    if all(status == SourceCandidate.Status.PROMOTED for status in candidate_statuses):
        return "succeeded"
    if all(status == SourceCandidate.Status.FAILED for status in candidate_statuses):
        return "failed"
    return "partial"


def _classify_event_outcome(*, attempted, failed, created_count):
    """이벤트 시도 결과를 없음/정상/실패/부분 중 하나로 분류한다.

    생성 0건이어도 실패가 없으면 정상이다(제외는 실패가 아니다).
    """
    if attempted == 0:
        return "none"
    if failed == 0:
        return "succeeded"
    if created_count == 0:
        return "failed"
    return "partial"


def _combine_outcomes(*, candidate_outcome, event_outcome):
    """후보 결과와 이벤트 결과를 실행 최종 상태로 결합한다."""
    existing = [
        outcome for outcome in (candidate_outcome, event_outcome) if outcome != "none"
    ]
    if not existing or all(outcome == "succeeded" for outcome in existing):
        return SourceDiscoveryRun.Status.SUCCEEDED
    if all(outcome == "failed" for outcome in existing):
        return SourceDiscoveryRun.Status.FAILED
    return SourceDiscoveryRun.Status.PARTIALLY_FAILED


def runner_is_online(*, status_row):
    """DiscoveryRunnerStatus 행(없으면 None)을 받아 신선도 판정을 소유한다."""
    if status_row is None:
        return False
    fresh = status_row.last_heartbeat_at >= timezone.now() - timedelta(
        seconds=HEARTBEAT_FRESH_SECONDS
    )
    # 오프라인 보고 이후 새 heartbeat가 없으면 신선해도 온라인으로 보지 않는다.
    recovered = status_row.offline_at is None or status_row.offline_at < status_row.last_heartbeat_at
    return fresh and recovered


def clean_heartbeat_detail(detail):
    """제어문자를 지우고 200자로 잘라 저장 가능한 진행 문구로 만든다."""
    # candidate_validation이 이 모듈을 임포트하므로 반대 방향은 함수 안에서만 쓴다.
    from drafts.candidate_validation import sanitize_text

    return sanitize_text(value=detail)[:200]


def record_offline():
    DiscoveryRunnerStatus.objects.filter(pk=1).update(offline_at=timezone.now())


def normalize_heartbeat_phase(phase):
    """어휘 밖 phase는 무시하고 경고만 남긴다 — 러너 원문을 그대로 믿지 않는다."""
    if phase is None:
        return None
    if phase not in DiscoveryRunnerStatus.Phase.values:
        logger.warning("invalid heartbeat phase: %s", phase)
        return None
    return phase


def record_heartbeat(*, provider, phase=None, detail=None, run_id=None):
    phase = normalize_heartbeat_phase(phase)
    now = timezone.now()
    defaults = {"last_heartbeat_at": now, "provider": provider}
    # phase가 없는 옛 러너 heartbeat는 이전 phase 값을 지우면 안 된다.
    if phase is not None:
        defaults["phase"] = phase
        defaults["phase_updated_at"] = now
    if detail is not None:
        defaults["phase_detail"] = clean_heartbeat_detail(detail)
    # 존재하지 않는 run_id는 조용히 무시한다 — 옛 실행이 만료된 사이 온
    # heartbeat가 FK 오류로 상태 갱신 전체를 실패시키면 안 된다.
    if run_id is not None and SourceDiscoveryRun.objects.filter(pk=run_id).exists():
        defaults["current_run_id"] = run_id
    DiscoveryRunnerStatus.objects.update_or_create(pk=1, defaults=defaults)


def create_run(*, requested_by, query=""):
    # 동시 요청 2건이 활성 검사~생성 사이에 끼어들어 pending 두 건을 만드는
    # 경쟁을 막는다 — heartbeat 단일 행(pk=1)을 잠가 자연스러운 직렬화
    # 지점으로 삼는다.
    with transaction.atomic():
        status = DiscoveryRunnerStatus.objects.select_for_update().filter(pk=1).first()
        if not runner_is_online(status_row=status):
            raise RunnerOfflineError

        active_statuses = [SourceDiscoveryRun.Status.PENDING, SourceDiscoveryRun.Status.CLAIMED]
        if SourceDiscoveryRun.objects.filter(status__in=active_statuses).exists():
            raise DiscoveryRunActiveError

        return SourceDiscoveryRun.objects.create(requested_by=requested_by, query=query)


def claim(*, provider):
    with transaction.atomic():
        # 별도 스케줄러 없이 다음 claim 시점에 만료 임대를 재대기시킨다(지연 정리).
        expired_runs = SourceDiscoveryRun.objects.select_for_update().filter(
            status=SourceDiscoveryRun.Status.CLAIMED,
            lease_expires_at__lt=timezone.now(),
        )
        for expired_run in expired_runs:
            if expired_run.lease_count >= MAX_LEASES:
                expired_run.status = SourceDiscoveryRun.Status.EXPIRED
                expired_run.finished_at = timezone.now()
                expired_run.lease_token = ""
                expired_run.save(update_fields=["status", "finished_at", "lease_token"])
            else:
                expired_run.status = SourceDiscoveryRun.Status.PENDING
                expired_run.lease_token = ""
                expired_run.save(update_fields=["status", "lease_token"])

        run = (
            SourceDiscoveryRun.objects.select_for_update()
            .filter(status=SourceDiscoveryRun.Status.PENDING)
            .order_by("created_at")
            .first()
        )
        if run is None:
            return None

        run.status = SourceDiscoveryRun.Status.CLAIMED
        run.provider = provider
        run.lease_token = uuid.uuid4().hex
        run.lease_expires_at = timezone.now() + timedelta(seconds=LEASE_SECONDS)
        run.lease_count += 1
        if run.started_at is None:
            run.started_at = timezone.now()
        run.save(
            update_fields=[
                "status",
                "provider",
                "lease_token",
                "lease_expires_at",
                "lease_count",
                "started_at",
            ]
        )
        return run


def locked_run_with_valid_lease(*, run_id, lease_token):
    run = SourceDiscoveryRun.objects.select_for_update().get(pk=run_id)
    if run.status != SourceDiscoveryRun.Status.CLAIMED:
        raise LeaseInvalidError
    if not constant_time_compare(run.lease_token, lease_token):
        raise LeaseInvalidError
    if run.lease_expires_at is None or run.lease_expires_at <= timezone.now():
        raise LeaseInvalidError
    return run


def renew_lease(*, run):
    # 유효 제출마다 호출돼 긴 검증 중 임대 만료로 제출이 거부되는 경로를 막는다.
    run.lease_expires_at = timezone.now() + timedelta(seconds=LEASE_SECONDS)
    run.save(update_fields=["lease_expires_at"])


def complete_run(
    *,
    run_id,
    lease_token,
    runner_status,
    failure_kind="",
    events_attempted=0,
    events_failed=0,
    events_excluded=0,
    event_outcomes=None,
):
    # agent_drafts가 모듈 최상단에서 discovery_runs를 임포트하므로, 여기서
    # 그 반대 방향을 모듈 최상단에 두면 순환 임포트가 된다 — 함수 안에서만 쓴다.
    from drafts.agent_drafts import MAX_EVENTS_PER_RUN

    cleaned_attempted = max(0, min(events_attempted, MAX_EVENTS_PER_RUN))
    cleaned_failed = max(0, min(events_failed, cleaned_attempted))
    cleaned_excluded = max(0, min(events_excluded, MAX_EVENTS_PER_RUN))

    with transaction.atomic():
        run = locked_run_with_valid_lease(run_id=run_id, lease_token=lease_token)

        if runner_status == "failed":
            error_summary = "러너가 실행 실패를 보고했다"
            # 허용 목록 밖 값은 무시한다 — 러너가 보낸 원문을 그대로 보간하지 않는다.
            if failure_kind in _ALLOWED_FAILURE_KINDS:
                error_summary = f"{error_summary} ({failure_kind})"
            # 러너가 실행 실패를 보고해도 그 전에 이미 승격된 후보는 실재하는
            # 성과다 — 스태프가 놓치지 않도록 실패가 아닌 부분 실패로 남긴다.
            if run.candidates.filter(status=SourceCandidate.Status.PROMOTED).exists():
                run.status = SourceDiscoveryRun.Status.PARTIALLY_FAILED
            else:
                run.status = SourceDiscoveryRun.Status.FAILED
            run.error_summary = error_summary
        else:
            # 후보 결과와 이벤트 결과 각각을 없음/정상/실패/부분으로 분류한
            # 뒤 결합한다 — 생성 수는 러너 보고가 아니라 실제 저장 수
            # (run.events)로 센다.
            candidate_statuses = list(run.candidates.values_list("status", flat=True))
            candidate_outcome = _classify_candidate_outcome(candidate_statuses)
            event_outcome = _classify_event_outcome(
                attempted=cleaned_attempted,
                failed=cleaned_failed,
                created_count=run.events.count(),
            )
            run.status = _combine_outcomes(
                candidate_outcome=candidate_outcome, event_outcome=event_outcome
            )

        run.finished_at = timezone.now()
        run.lease_token = ""
        run.events_attempted = cleaned_attempted
        run.events_failed = cleaned_failed
        run.events_excluded = cleaned_excluded
        known_created_urls = set(run.events.values_list("source_url", flat=True))
        run.event_outcomes = _clean_event_outcomes(
            event_outcomes, known_created_urls=known_created_urls
        )
        run.save(
            update_fields=[
                "status",
                "error_summary",
                "finished_at",
                "lease_token",
                "events_attempted",
                "events_failed",
                "events_excluded",
                "event_outcomes",
            ]
        )
        return run
