"""Public read layer for events.

Provides reusable filter/order logic that both the JSON API (events/views.py)
and the upcoming SSR views (core/views.py) can call without duplicating
validation or query construction.
"""
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
        .order_for_public_listing(today=today)
    )
