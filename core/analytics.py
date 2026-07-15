"""core.analytics — behavioral event recording (PR-0e, G16/F-07).

Cross-domain concern: events/archive call `record_event` to log the 8
stage-0 behavioral events (see AnalyticsEvent.EventName) without any domain
depending on the others through this module. `core` is the existing
shared-dependency leaf every domain app already imports from, so this stays
here rather than a new app.

Privacy: `pseudonymous_user_key` never stores or derives from the raw user
pk in a reversible way (see its docstring). `record_event` hard-fails on a
context key that could carry personal data (free text, contact info, media
URLs) — see FORBIDDEN_CONTEXT_KEYS.
"""
import hashlib
import hmac
import logging
from datetime import timedelta

from django.conf import settings
from django.db.models import Count
from django.utils import timezone

from core.models import AnalyticsEvent


logger = logging.getLogger(__name__)

# Context keys that could carry personal data (free text a user typed,
# contact info, or a media URL) are refused outright rather than silently
# stored — see record_event.
FORBIDDEN_CONTEXT_KEYS = frozenset({"short_review", "note", "email", "photo_url", "image"})


def pseudonymous_user_key(user):
    """Return a deterministic, non-reversible per-user cohort key.

    HMAC-SHA256(SECRET_KEY, str(user.pk)), truncated to 32 hex chars. Keyed
    by SECRET_KEY (not a separate constant) so no new secret needs
    provisioning/rotation — the accepted tradeoff (per approved design) is
    that rotating SECRET_KEY silently breaks cohort continuity across the
    rotation; that is acceptable for this metrics use case, which does not
    require raw-key rotation resilience.

    Returns "" for an anonymous/unauthenticated user (no pk to key on) —
    callers must treat "" as "no cohort", not a shared cohort of anonymous
    hits.
    """
    if not getattr(user, "pk", None):
        return ""
    digest = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        str(user.pk).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:32]


def record_event(event_name, *, user, target_type="", target_id=None, context=None):
    """Record one AnalyticsEvent row. Never raises.

    A forbidden context key (FORBIDDEN_CONTEXT_KEYS) is a hard failure
    (ValueError), raised *before* any persistence attempt — this is a
    programming-error guard against accidentally logging personal data, not
    a runtime condition callers should recover from.

    Persistence itself is best-effort: analytics must never break the
    domain action it is attached to (e.g. creating a visit record), so a
    persistence failure (e.g. a DB outage) is caught and logged, not
    raised.
    """
    context = context or {}
    forbidden = FORBIDDEN_CONTEXT_KEYS & context.keys()
    if forbidden:
        raise ValueError(
            f"context contains forbidden key(s): {', '.join(sorted(forbidden))}"
        )

    try:
        AnalyticsEvent.objects.create(
            event_name=event_name,
            user_key=pseudonymous_user_key(user),
            target_type=target_type,
            target_id=target_id,
            context=context,
        )
    except Exception:
        logger.exception("Failed to record analytics event %r", event_name)


def distinct_user_key_count_since(days=7):
    """Count of distinct non-empty (identified) user_key values recorded in
    the trailing `days` days. "" (anonymous, see pseudonymous_user_key) is
    excluded — it does not represent one shared cohort."""
    window_start = timezone.now() - timedelta(days=days)
    return (
        AnalyticsEvent.objects.filter(created_at__gte=window_start)
        .exclude(user_key="")
        .values("user_key")
        .distinct()
        .count()
    )


def event_name_counts_since(days=7):
    """Return {event_name: count} for events recorded in the trailing
    `days` days. An event_name with zero rows in the window is simply
    absent from the returned dict."""
    window_start = timezone.now() - timedelta(days=days)
    rows = (
        AnalyticsEvent.objects.filter(created_at__gte=window_start)
        .values("event_name")
        .annotate(count=Count("id"))
    )
    return {row["event_name"]: row["count"] for row in rows}
