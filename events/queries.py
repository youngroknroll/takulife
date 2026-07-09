"""Public read layer for events.

Provides reusable filter/order logic that both the JSON API (events/views.py)
and the upcoming SSR views (core/views.py) can call without duplicating
validation or query construction.
"""
from django.db import models
from django.utils import timezone

from .models import Event
from .serializers import EventQuerySerializer

PUBLIC_LISTING_PAGE_SIZE = 10

# Filters that accept repeated values (?region=a&region=b) and OR them together.
MULTI_VALUE_FIELDS = ("region", "category")


def _collect_values(raw_params, key):
    """Return non-blank values for key as a list.

    Uses getlist() when available (DRF query_params / Django QueryDict) so
    repeated params are preserved; falls back to a single value for plain dicts.
    """
    getlist = getattr(raw_params, "getlist", None)
    values = getlist(key) if callable(getlist) else [raw_params.get(key)]
    return [value for value in values if value not in (None, "")]


def parse_public_listing_params(raw_params):
    """Parse and validate public listing query parameters from any Mapping.

    Accepts DRF request.query_params or Django request.GET.
    Drops unknown keys (including 'page') and validates via EventQuerySerializer.
    region/category collect repeated values into a list; other fields take a
    single value. Blank values are dropped so an empty filter (e.g. the "전체"
    status radio / default sort the browse form always submits) means "no
    filter" rather than failing ChoiceField/DateField validation.
    Returns validated_data dict on success, raises ValidationError on failure.
    """
    allowed_fields = EventQuerySerializer().fields
    data = {}
    for key in allowed_fields:
        if key in MULTI_VALUE_FIELDS:
            values = _collect_values(raw_params, key)
            if values:
                data[key] = values
        else:
            value = raw_params.get(key)
            if value not in (None, ""):
                data[key] = value

    serializer = EventQuerySerializer(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def list_published_events(params, *, today=None):
    """Return an ordered QuerySet of published events filtered by params.

    params: validated_data dict from parse_public_listing_params (or equivalent).
    today: date override for testing; defaults to timezone.localdate().
    """
    if today is None:
        today = timezone.localdate()
    return (
        Event.objects.published()
        .filter_for_public_listing(params, today=today)
        .order_for_public_listing(today=today, sort=params.get("sort"))
    )


# ---------------------------------------------------------------------------
# Staff dashboard quality-warning counters (PR-1b) + drilldown (PR-E1)
#
# Each _*_qs() helper is the single source of truth for one warning's
# predicate over Event.objects.published(). count_published_* wraps it in
# .count() (dashboard summary); list_staff_events() (below) reuses the same
# queryset for the drilldown list, so the two are guaranteed to agree on
# population by construction — no duplicated predicate logic.
# ---------------------------------------------------------------------------


def _missing_official_url_qs():
    return Event.objects.published().filter(models.Q(official_url__isnull=True) | models.Q(official_url=""))


def _ended_still_published_qs(*, today=None):
    if today is None:
        today = timezone.localdate()
    return Event.objects.published().filter(end_date__lt=today)


def _missing_poster_qs():
    return Event.objects.published().filter(models.Q(poster_image__isnull=True) | models.Q(poster_image=""))


def _missing_dates_qs():
    return Event.objects.published().filter(models.Q(start_date__isnull=True) | models.Q(end_date__isnull=True))


def _missing_region_qs():
    """Published events with region == "" exactly.

    Conscious v1 decision: no strip/normalization, so a whitespace-only
    region (e.g. " ") is NOT counted here.
    """
    return Event.objects.published().filter(region="")


def count_published_missing_official_url() -> int:
    """Count published events with no official_url (NULL or blank)."""
    return _missing_official_url_qs().count()


def count_published_ended_still_published(*, today=None) -> int:
    """Count published events whose end_date is strictly before today.

    today: date override for testing; defaults to timezone.localdate().
    Events with a null end_date never match (open-ended events are not
    considered "ended").
    """
    return _ended_still_published_qs(today=today).count()


def count_published_missing_poster() -> int:
    """Count published events with no poster_image (blank and/or null)."""
    return _missing_poster_qs().count()


def count_published_missing_dates() -> int:
    """Count published events missing start_date and/or end_date.

    Counted once even when both are null (OR, not a sum of two conditions).
    """
    return _missing_dates_qs().count()


def count_published_missing_region() -> int:
    """Count published events with region == "" exactly.

    Conscious v1 decision: no strip/normalization, so a whitespace-only
    region (e.g. " ") is NOT counted here.
    """
    return _missing_region_qs().count()


def published_quality_warnings(*, today=None) -> dict:
    """Return quality-warning counts for the staff dashboard as a dict.

    All 5 per-predicate keys are always present, even when a given warning
    has zero matches. today is forwarded only to the ended-still-published
    check.

    "total" is the SUM of the 5 warning counts above (flags tripped), not a
    count of distinct events. This keeps it consistent with the dashboard's
    visible 5-row breakdown (total == row sum): an event tripping 2
    predicates contributes 2 to total. It is computed from the 5 values
    already gathered here, so no extra query is run.
    """
    missing_official_url = count_published_missing_official_url()
    ended_still_published = count_published_ended_still_published(today=today)
    missing_poster = count_published_missing_poster()
    missing_dates = count_published_missing_dates()
    missing_region = count_published_missing_region()
    return {
        "missing_official_url": missing_official_url,
        "ended_still_published": ended_still_published,
        "missing_poster": missing_poster,
        "missing_dates": missing_dates,
        "missing_region": missing_region,
        "total": (
            missing_official_url
            + ended_still_published
            + missing_poster
            + missing_dates
            + missing_region
        ),
    }


# ---------------------------------------------------------------------------
# Staff events console listing (PR-E1)
# ---------------------------------------------------------------------------

QUALITY_WARNING_KEYS = (
    "missing_official_url",
    "ended_still_published",
    "missing_poster",
    "missing_dates",
    "missing_region",
)

STAFF_EVENT_LISTING_PAGE_SIZE = 10

_NON_DATED_WARNING_QUERYSETS = {
    "missing_official_url": _missing_official_url_qs,
    "missing_poster": _missing_poster_qs,
    "missing_dates": _missing_dates_qs,
    "missing_region": _missing_region_qs,
}


def list_staff_events(*, warning=None, publish_status=None, today=None):
    """Return Events for the staff events console, newest (created_at) first.

    warning: one of QUALITY_WARNING_KEYS scopes the result to the exact same
      published-only queryset the matching count_published_* function counts
      (drilldown parity — see the block comment above those helpers). Any
      other value (None, "", or an unrecognised key) is silently ignored —
      no warning filter is applied — mirroring the existing
      selected_status/selected_warning normalisation pattern used by staff
      views rather than raising for a bad querystring value.
    publish_status: an Event.PublishStatus value restricts the result to
      that status. Any other value (None, "", unrecognised) is ignored (all
      statuses included). Note a warning filter is already published-only by
      construction, so pairing it with publish_status=draft yields an empty
      queryset rather than an error.
    today: date override forwarded only to the ended_still_published
      warning (see _ended_still_published_qs); ignored otherwise.
    """
    if warning == "ended_still_published":
        queryset = _ended_still_published_qs(today=today)
    elif warning in _NON_DATED_WARNING_QUERYSETS:
        queryset = _NON_DATED_WARNING_QUERYSETS[warning]()
    else:
        queryset = Event.objects.all()

    if publish_status in Event.PublishStatus.values:
        queryset = queryset.filter(publish_status=publish_status)

    return queryset.order_by("-created_at")
