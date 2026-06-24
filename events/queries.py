"""Public read layer for events.

Provides reusable filter/order logic that both the JSON API (events/views.py)
and the upcoming SSR views (core/views.py) can call without duplicating
validation or query construction.
"""
from django.utils import timezone

from .models import Event
from .serializers import EventQuerySerializer

PUBLIC_LISTING_PAGE_SIZE = 20


def parse_public_listing_params(raw_params):
    """Parse and validate public listing query parameters from any Mapping.

    Accepts DRF request.query_params or Django request.GET.
    Drops unknown keys (including 'page') and validates via EventQuerySerializer.
    Returns validated_data dict on success, raises ValidationError on failure.
    """
    allowed_fields = EventQuerySerializer().fields
    data = {
        key: value
        for key, value in raw_params.items()
        if key in allowed_fields
    }
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
