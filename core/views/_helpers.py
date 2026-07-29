"""여러 뷰 그룹(이벤트/활동/아카이브/컬렉션)이 함께 쓰는 표시·조회 헬퍼."""

from datetime import datetime

from django.shortcuts import render
from django.utils import timezone

from archive.models import UserEventStatus
from archive.queries import user_interest_event_ids
from core.calendar_grid import default_selected_date
from core.vocab import ARCHIVE_STATUS_LABELS, CATEGORY_LABELS, EVENT_STATUS_LABELS, REGION_LABELS
from events.presenters import derive_event_display, is_recently_added


def _archive_query(request) -> str:
    """Extract and normalise the ?q= search term from the request.

    Strips surrounding whitespace and truncates at 100 characters so an
    arbitrarily long q value never inflates query time or causes errors.
    """
    return (request.GET.get("q") or "").strip()[:100]


def _attach_display(events, *, today=None, user=None):
    """Attach derived display (status_slug, status_label, dday) to each event.

    When ``user`` is an authenticated user, also attaches ``user_status`` — the
    user's own archive status slug for that event ("" if none) — so discovery
    cards can reflect real state instead of a fixed default.

    Returns a list of plain dicts so templates can use dot notation cleanly.
    """
    events = list(events)
    event_ids = [event.id for event in events]

    user_status_map = {}
    user_interest_map = {}
    if user is not None and user.is_authenticated and events:
        status_today = today if today is not None else timezone.localdate()
        user_status_map = {
            event_id: (status_val, status_id)
            for event_id, status_val, status_id in (
                UserEventStatus.objects.filter(user=user, event_id__in=event_ids)
                .with_derived_status(today=status_today)
                .values_list("event_id", "derived_status", "id")
            )
        }
        user_interest_map = user_interest_event_ids(user, event_ids=event_ids)

    result = []
    for event in events:
        display = derive_event_display(event, today=today)
        status_slug = display["status"]
        user_status, user_status_id = user_status_map.get(event.id, ("", None))
        interest_id = user_interest_map.get(event.id)
        result.append(
            {
                "event": event,
                "status_slug": status_slug,
                "status_label": EVENT_STATUS_LABELS.get(status_slug, ""),
                "category_label": CATEGORY_LABELS.get(event.category, event.category),
                "category_slug": event.category,
                "region_label": REGION_LABELS.get(event.region, "") if event.region else "",
                "dday": display["dday"],
                "is_new": is_recently_added(event, today=today),
                "user_status": user_status,
                "user_status_id": user_status_id,
                "user_status_label": ARCHIVE_STATUS_LABELS.get(user_status, ""),
                "user_interested": interest_id is not None,
                "user_interest_id": interest_id,
            }
        )
    return result


def _adjacent_month(year, month, delta):
    """Return the (year, month) `delta` months away from (year, month),
    wrapping across year boundaries (delta is typically -1 or +1)."""
    total = year * 12 + (month - 1) + delta
    new_year, new_month0 = divmod(total, 12)
    return new_year, new_month0 + 1


def _parse_calendar_month(raw_month, *, today):
    """Parse the ?month=YYYY-MM param. Returns (year, month, error) where
    error is None on success or "invalid" on a malformed/out-of-range value.

    Only a truly *absent* key (raw_month is None) defaults to today's month
    (service design §11.1: "month 부재는 오류가 아니며 당월을 표시한다") —
    a key that is *present* with a blank value (?month=) is itself a format
    error ("month 형식 오류(...,빈 값)는... 오류 패널"), not "absent". The
    caller must pass request.GET.get("month") with no default so this
    function can see that distinction; collapsing both cases to "" here
    would silently treat `?month=` the same as no `month` key at all.
    """
    if raw_month is None:
        return today.year, today.month, None
    try:
        parsed = datetime.strptime(raw_month, "%Y-%m")
    except ValueError:
        return None, None, "invalid"
    return parsed.year, parsed.month, None


def _parse_calendar_date(raw_date, *, year, month, today):
    """Parse the ?date=YYYY-MM-DD param against the already-resolved
    (year, month). Returns (date, error) where error is None on success or
    "invalid" for a malformed value, a nonexistent calendar date, or a date
    outside the displayed month (service design §11.1).

    Only a truly *absent* key (raw_date is None) falls back to
    CAL-4-04/05's default-selection rule — a *present* blank value
    (?date=) is a format error, mirroring _parse_calendar_month's same
    absent-vs-blank distinction. The caller must pass
    request.GET.get("date") with no default.
    """
    if raw_date is None:
        return default_selected_date(year=year, month=month, today=today), None
    try:
        parsed = datetime.strptime(raw_date, "%Y-%m-%d").date()
    except ValueError:
        return None, "invalid"
    if (parsed.year, parsed.month) != (year, month):
        return None, "invalid"
    return parsed, None


def _render_archive_list(request, *, full_template, fragment_template, context):
    """Render an archive list page, or just its results fragment for live search.

    When the request carries ``?partial=1`` the live-search JS only wants the
    swappable results region (list + empty states + pager), so the fragment
    template is rendered alone instead of the full page. The calling view's
    auth/CSRF decorators still apply — this is an internal branch, not a
    separate unauthenticated endpoint. Any other value (or none) renders the
    full page, so the no-JS GET form keeps working unchanged.
    """
    template = fragment_template if request.GET.get("partial") == "1" else full_template
    return render(request, template, context)


def _subject_view(obj):
    """Uniform, null-safe view of an archive row's subject — an official Event
    or an unofficial PersonalEntry.

    Any archive row that carries the subject pattern (VisitRecord, EventInterest,
    UserEventStatus) exposes ``event``/``event_id`` and ``personal_entry``; this
    collapses both into one dict so templates and JS never branch on which FK is
    set. ``subject_type``/``subject_id`` drive the API payload; ``detail_url`` is
    empty for private items (no public page); period dates are None for goods.
    """
    if obj.event_id is not None:
        event = obj.event
        return {
            "title": event.title,
            "category_label": CATEGORY_LABELS.get(event.category, event.category),
            "category_slug": event.category,
            "location": event.location_name,
            "start_date": event.start_date,
            "end_date": event.end_date,
            "is_official": True,
            "kind": "",
            "subject_type": "event",
            "subject_id": event.id,
            "detail_url": f"/events/{event.id}/",
        }
    entry = obj.personal_entry
    return {
        "title": entry.title,
        "category_label": entry.category,
        "location": entry.location_name,
        "start_date": None,
        "end_date": None,
        "is_official": False,
        "kind": entry.kind,
        "subject_type": "personal",
        "subject_id": entry.id,
        "detail_url": "",
    }
