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
# Staff dashboard quality-warning counters (PR-1b)
#
# Each function is a thin, independent count over Event.objects.published().
# These are one-off counts for a single consumer (the staff dashboard), so the
# predicate filters live here rather than as reusable queryset methods.
# ---------------------------------------------------------------------------


def count_published_missing_official_url() -> int:
    """Count published events with no official_url (NULL or blank)."""
    return Event.objects.published().filter(models.Q(official_url__isnull=True) | models.Q(official_url="")).count()


def count_published_ended_still_published(*, today=None) -> int:
    """Count published events whose end_date is strictly before today.

    today: date override for testing; defaults to timezone.localdate().
    Events with a null end_date never match (open-ended events are not
    considered "ended").
    """
    if today is None:
        today = timezone.localdate()
    return Event.objects.published().filter(end_date__lt=today).count()


def count_published_missing_poster() -> int:
    """Count published events with no poster_image (blank and/or null)."""
    return Event.objects.published().filter(models.Q(poster_image__isnull=True) | models.Q(poster_image="")).count()


def count_published_missing_dates() -> int:
    """Count published events missing start_date and/or end_date.

    Counted once even when both are null (OR, not a sum of two conditions).
    """
    return (
        Event.objects.published()
        .filter(models.Q(start_date__isnull=True) | models.Q(end_date__isnull=True))
        .count()
    )


def count_published_missing_region() -> int:
    """Count published events with region == "" exactly.

    Conscious v1 decision: no strip/normalization, so a whitespace-only
    region (e.g. " ") is NOT counted here.
    """
    return Event.objects.published().filter(region="").count()


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
