"""Staff Console views.

PR-2 sub-step D: the 3 draft/home-category SSR views (previously routed
through core.views for a smaller PR-1a diff) now live here permanently,
alongside the draft approve/reject action endpoints. staff -> core is an
allowed presentation-only import (label maps/vocab); core must never import
staff back (see tests/test_architecture_boundaries.py).
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


# Korean labels for every StaffActionLog.Action value, keyed by the raw
# action string (mirrors QUALITY_WARNING_LABELS below). get_action_display()
# is intentionally not used here — it would surface the model's English
# choice labels, and this dict keeps the audit trail's display language
# separate from the model definition (see StaffActionLog.Action).
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
    """Attach a Korean action_label to each StaffActionLog row for the
    dashboard's "최근 처리 내역" table.

    Mirrors _build_draft_rows/_build_event_rows: nests the log object under
    "log" plus a derived display-only field, rather than mutating the log
    object itself.
    """
    return [
        {"log": action, "action_label": ACTION_LABELS.get(action.action, action.action)}
        for action in actions
    ]


def _build_source_rows(sources):
    """Attach derived freshness state to each DraftSource row for the
    dashboard's "수집 소스 상태" table.

    has_error is a plain last_error truthiness check. is_stale only applies
    to enabled sources (a disabled source is not expected to be collecting,
    so a stale last_checked_at there is not a problem) — never checked
    (last_checked_at is None) and older than DRAFT_SOURCE_STALE_HOURS both
    count as stale.

    status_level derives from has_error/is_stale (not a separate check)
    so the status dot can never disagree with the badges rendered next to
    it. Priority when several are true at once: disabled > error > stale >
    ok — a disabled source is never miscolored as erroring, and an actively
    failing source is flagged over a merely-stale one (see PR-D1 item 3:
    never-checked + last_error can both be true simultaneously).
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
    """Attach display rows to the quality_warnings dict for the dashboard's
    "품질 경고" bar list, sorted count descending.

    Ties are broken by QUALITY_WARNING_LABELS' definition order rather than
    left to sort() to decide arbitrarily: enumerate() captures each row's
    original position before sorting, and that position becomes the
    secondary sort key (the worst warning must
    always be first, and tied warnings must render in a stable order across
    requests).
    """
    rows = [
        {"key": key, "label": label, "count": warnings[key]}
        for key, label in QUALITY_WARNING_LABELS.items()
    ]
    ranked = sorted(enumerate(rows), key=lambda pair: (-pair[1]["count"], pair[0]))
    return [row for _, row in ranked]


def _build_activity_columns(per_day):
    """Attach chart-ready fields to each staff_actions_per_day() row for the
    dashboard's "최근 14일 활동" column chart.

    height_pct is computed here (not in the template) against the window's
    own max count, so a day with the most activity always renders at 100%
    and every other day scales relative to it; if every day is 0 (e.g. no
    logs at all), every height_pct is 0 rather than dividing by zero.
    is_today marks the last row via an explicit date comparison — per_day's
    ordering already guarantees the last row *is* today, but comparing
    against timezone.localdate() here keeps that guarantee from being a
    silent assumption baked only into staff_actions_per_day's contract.
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
    """Return the most recent DRAFT_DISCOVER StaffActionLog's created_at, or
    None if discovery has never been run.

    Reads StaffActionLog directly (not DraftSource.last_checked_at max) so
    the "마지막 실행" summary is accurate even when a run touched zero
    sources (e.g. all sources disabled) — the log entry is written on every
    non-flag-off run regardless of outcome (see staff_draft_discovery_run).
    """
    log = (
        StaffActionLog.objects.filter(action=StaffActionLog.Action.DRAFT_DISCOVER)
        .order_by("-created_at")
        .first()
    )
    return log.created_at if log else None


@staff_console_required
def dashboard(request):
    """Staff console landing page."""
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
            # Explicit key rather than `{{ activity_columns|last }}.count` in
            # the template — Django's `|last.count` filter/attribute chaining
            # isn't valid template syntax.
            "activity_today_count": (
                activity_columns[-1]["count"] if activity_columns else 0
            ),
        },
    )


@staff_console_required
def staff_draft_discovery_run(request):
    """Staff console: run `discover_drafts` synchronously from the dashboard's
    "수집 소스 상태" panel ("지금 수집" button — prompt_plan.md's 콘솔 수집
    실행 버튼).

    GET is redirected to the dashboard rather than @require_POST's 405: a
    session that expires mid-click bounces the browser through
    accounts/login?next=<this URL>, and login's own redirect issues a GET —
    turning what should be a re-auth prompt into a dead-end 405 page. This
    mirrors the flag-off short-circuit below (also just an info redirect,
    no command execution).

    `DRAFT_DISCOVERY_ENABLED=False` and a zero-enabled-source DraftSource
    table are both short-circuited here, before the command even runs (the
    command itself already no-ops in either case — see discover_drafts.py's
    own module docstring — but the view pre-empts it so the intent is
    explicit) and neither writes an audit log entry, since nothing actually
    executed. Every path that *does* invoke the command (success, a
    partial-failure CommandError, or an unclassified exception) is
    audit-logged, because from an operator's point of view a run was
    attempted regardless of its outcome. Runs synchronously and can take
    tens of seconds depending on source/candidate count (see "하지 말 것":
    no celery/threads/subprocess/lock/progress UI for this button).
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
    """Collapse discover_drafts' multi-line stdout into one message-friendly
    line (django.contrib.messages renders as plain text — no <br>, so
    newlines would otherwise just run together)."""
    lines = [line for line in out.getvalue().splitlines() if line.strip()]
    return " · ".join(lines)
