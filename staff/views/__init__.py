"""스태프 콘솔 뷰.

staff가 core를 임포트하는 것(라벨 맵/어휘 등 표시용)은 허용되지만,
core가 staff를 거꾸로 임포트해서는 안 된다(tests/test_architecture_boundaries.py).
"""
import datetime
import logging
from io import StringIO

from django.conf import settings
from django.contrib import messages
from django.core.management import CommandError, call_command
from django.shortcuts import redirect, render
from django.utils import timezone

from core.analytics import distinct_user_key_count_since, event_name_counts_since
from drafts.queries import (
    draft_review_stats,
    enabled_draft_sources_exist,
    list_draft_sources,
)
from events.queries import published_quality_warnings

from ..models import StaffActionLog
from ..permissions import staff_console_required
from ..queries import (
    recent_staff_actions,
    staff_actions_count_since,
    staff_actions_per_day,
)
from ._helpers import _action_log_kwargs, _staff_action_metadata
from .drafts import (
    MAX_BULK_APPROVE_DRAFT_IDS,
    StaffDraftApproveView,
    StaffDraftBulkApproveView,
    StaffDraftRejectView,
    event_draft_detail,
    event_drafts,
)
from .events import (
    EVENT_CREATE_BLANK_FORM_VALUES,
    EVENT_EDIT_TEXT_FIELDS,
    QUALITY_WARNING_LABELS,
    staff_event_create,
    staff_event_delete,
    staff_event_edit,
    staff_event_toggle_publish,
    staff_event_verify,
    staff_events,
)
from .home_categories import staff_home_categories

__all__ = [
    "ACTION_LABELS",
    "dashboard",
    "staff_draft_discovery_run",
    "EVENT_CREATE_BLANK_FORM_VALUES",
    "EVENT_EDIT_TEXT_FIELDS",
    "QUALITY_WARNING_LABELS",
    "staff_event_create",
    "staff_event_delete",
    "staff_event_edit",
    "staff_event_toggle_publish",
    "staff_event_verify",
    "staff_events",
    "MAX_BULK_APPROVE_DRAFT_IDS",
    "StaffDraftApproveView",
    "StaffDraftBulkApproveView",
    "StaffDraftRejectView",
    "event_draft_detail",
    "event_drafts",
    "staff_home_categories",
]

logger = logging.getLogger(__name__)


# get_action_display()를 쓰지 않는다 — 모델의 영어 choice 라벨이 그대로
# 노출되므로, 화면에 보일 한국어 라벨은 모델 정의와 분리해 여기서 관리한다.
ACTION_LABELS = {
    "approve": "승인",
    "reject": "반려",
    "home_categories": "홈 카테고리 변경",
    "event_update": "이벤트 수정",
    "event_create": "이벤트 생성",
    "event_unpublish": "게시 내리기",
    "event_republish": "재게시",
    "event_delete": "이벤트 삭제",
    "draft_discover": "드래프트 수집 실행",
}


def _build_action_rows(actions):
    """로그 객체를 직접 바꾸지 않고 "log" 키 아래에 감싼 뒤 표시용
    action_label을 덧붙인다."""
    return [
        {"log": action, "action_label": ACTION_LABELS.get(action.action, action.action)}
        for action in actions
    ]


def _build_source_rows(sources):
    """소스별 신선도 상태를 계산해 붙인다.

    is_stale는 활성화된 소스에만 적용한다 — 비활성 소스는 원래 수집을
    안 하므로 오래된 last_checked_at이 문제가 아니다. 여러 조건이 동시에
    참일 때 우선순위는 disabled > error > stale > ok다 — 비활성 소스가
    오류로 잘못 표시되지 않게 하고, 실제로 실패 중인 소스를 단순 정체보다
    먼저 알리기 위해서다.
    """
    cutoff = timezone.now() - datetime.timedelta(hours=settings.DRAFT_SOURCE_STALE_HOURS)
    rows = []
    for source in sources:
        has_error = bool(source.last_error)
        is_stale = source.enabled and (
            source.last_checked_at is None or source.last_checked_at < cutoff
        )
        if not source.enabled:
            status_level = "disabled"
        elif has_error:
            status_level = "error"
        elif is_stale:
            status_level = "stale"
        else:
            status_level = "ok"
        rows.append(
            {
                "source": source,
                "has_error": has_error,
                "is_stale": is_stale,
                "status_level": status_level,
            }
        )
    return rows


def _build_quality_warning_rows(warnings):
    """건수 내림차순으로 정렬한다.

    건수가 같으면 QUALITY_WARNING_LABELS에 정의된 순서를 따르게 해 요청마다
    순서가 흔들리지 않도록 한다.
    """
    rows = [
        {"key": key, "label": label, "count": warnings[key]}
        for key, label in QUALITY_WARNING_LABELS.items()
    ]
    ranked = sorted(enumerate(rows), key=lambda pair: (-pair[1]["count"], pair[0]))
    return [row for _, row in ranked]


def _build_activity_columns(per_day):
    """막대 그래프용 필드를 붙인다.

    height_pct는 구간 내 최댓값 대비 비율이라 가장 활발한 날이 항상 100%가
    되고, 로그가 전혀 없으면 0으로 나누는 대신 전부 0이 된다. is_today는
    정렬 순서에만 기대지 않고 오늘 날짜와 직접 비교해 정한다.
    """
    max_count = max((row["count"] for row in per_day), default=0)
    today = timezone.localdate()
    return [
        {
            "date": row["date"],
            "count": row["count"],
            "height_pct": (
                round(row["count"] / max_count * 100) if max_count else 0
            ),
            "is_today": row["date"] == today,
        }
        for row in per_day
    ]


def _last_discovery_run_at():
    """가장 최근 수집 실행 시각을 반환한다. 실행 이력이 없으면 None이다.

    DraftSource.last_checked_at 대신 StaffActionLog를 직접 읽는다 —
    소스를 하나도 건드리지 못한 실행(예: 전부 비활성)에서도 로그는
    남기 때문에 "마지막 실행" 표시가 어긋나지 않는다.
    """
    log = (
        StaffActionLog.objects.filter(action=StaffActionLog.Action.DRAFT_DISCOVER)
        .order_by("-created_at")
        .first()
    )
    return log.created_at if log else None


@staff_console_required
def dashboard(request):
    """스태프 콘솔 첫 화면."""
    stats = draft_review_stats()
    recent_actions = recent_staff_actions()
    draft_sources = list_draft_sources()
    quality_warnings = published_quality_warnings()
    quality_warning_rows = _build_quality_warning_rows(quality_warnings)
    activity_columns = _build_activity_columns(staff_actions_per_day(days=14))
    return render(
        request,
        "staff/dashboard.html",
        {
            "pending_count": stats["pending"],
            "quality_warnings": quality_warnings,
            "quality_warning_rows": quality_warning_rows,
            "quality_warning_max": max(
                (row["count"] for row in quality_warning_rows), default=0
            ),
            "recent_actions": recent_actions,
            "recent_action_rows": _build_action_rows(recent_actions),
            "draft_sources": draft_sources,
            "draft_source_rows": _build_source_rows(draft_sources),
            "draft_discovery_enabled": settings.DRAFT_DISCOVERY_ENABLED,
            "last_discovery_run_at": _last_discovery_run_at(),
            "recent_actions_7d_count": staff_actions_count_since(days=7),
            "recent_actions_prev_7d_count": staff_actions_count_since(days=7, offset=7),
            "weekly_active_user_count": distinct_user_key_count_since(days=7),
            "weekly_event_count": sum(event_name_counts_since(days=7).values()),
            "activity_columns": activity_columns,
            "activity_total_14d": sum(col["count"] for col in activity_columns),
            # 템플릿에서 `|last.count` 같은 필터+속성 체이닝은 문법상
            # 안 되므로 별도 키로 미리 계산해 넘긴다.
            "activity_today_count": (
                activity_columns[-1]["count"] if activity_columns else 0
            ),
        },
    )


@staff_console_required
def staff_draft_discovery_run(request):
    """대시보드 "지금 수집" 버튼에서 `discover_drafts`를 동기로 실행한다.

    GET은 405 대신 대시보드로 돌려보낸다 — 클릭 중 세션이 만료되면
    로그인 리다이렉트가 GET으로 돌아오는데, 그때 405 막다른 페이지가
    뜨지 않게 하기 위해서다. 기능 꺼짐이나 활성 소스 없음일 때도 명령을
    돌리지 않고 여기서 먼저 걸러내며, 이 경우엔 실제로 아무것도 실행되지
    않았으므로 감사 로그를 남기지 않는다. 반면 명령이 실제로 실행된
    모든 경로(성공/부분 실패/예외)는 결과와 무관하게 감사 로그를 남긴다.
    소스·후보 개수에 따라 수십 초 걸릴 수 있는 동기 실행이다.
    """
    if request.method != "POST":
        return redirect("staff:dashboard")

    if not settings.DRAFT_DISCOVERY_ENABLED:
        messages.info(
            request,
            "수집 기능이 비활성화되어 있습니다(DRAFT_DISCOVERY_ENABLED=False).",
        )
        return redirect("staff:dashboard")

    if not enabled_draft_sources_exist():
        messages.info(
            request,
            "활성 수집 소스가 없습니다. Django admin에서 소스를 활성화하세요.",
        )
        return redirect("staff:dashboard")

    out = StringIO()
    action = StaffActionLog.Action.DRAFT_DISCOVER
    try:
        call_command("discover_drafts", stdout=out)
    except CommandError as exc:
        summary = _summarize_command_output(out)
        messages.error(request, f"수집이 부분적으로 실패했습니다: {exc}" + (f" ({summary})" if summary else ""))
    except Exception:
        logger.exception("Unexpected error while running discover_drafts")
        messages.error(request, "수집 실행 중 오류가 발생했습니다.")
    else:
        summary = _summarize_command_output(out)
        messages.success(request, f"수집 완료: {summary}" if summary else "수집이 완료되었습니다.")
    finally:
        StaffActionLog.objects.create(
            **_action_log_kwargs(_staff_action_metadata(request), action)
        )

    return redirect("staff:dashboard")


def _summarize_command_output(out):
    """여러 줄 stdout을 한 줄로 합친다 — messages는 순수 텍스트로만 렌더링돼
    줄바꿈이 그대로는 이어 붙어 버린다."""
    lines = [line for line in out.getvalue().splitlines() if line.strip()]
    return " · ".join(lines)
