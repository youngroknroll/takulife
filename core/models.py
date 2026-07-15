"""core/models.py — Home page configuration model.

Singleton HomeConfig stores staff-curated category display settings.
Business rules (fallback, vocab validation, ordering) live here, not in views.
"""
from django.db import models

from core.vocab import CATEGORY, CATEGORY_LABELS


class HomeConfig(models.Model):
    """Singleton configuration for home page category display.

    featured_categories: ordered list of category slugs selected by staff.
    Empty list = show all vocab categories in vocab order (backward-compat fallback).
    """

    featured_categories = models.JSONField(default=list)

    class Meta:
        verbose_name = "Home page configuration"

    @classmethod
    def get_solo(cls):
        """Return the singleton instance (pk=1), creating it if needed."""
        instance, _ = cls.objects.get_or_create(pk=1)
        return instance

    def featured_category_pairs(self):
        """Return (slug, label) pairs for the featured categories.

        - Empty featured_categories → full CATEGORY vocab in vocab order (fallback).
        - Non-empty → stored slugs in stored order; slugs absent from vocab are
          silently dropped (validation guard).
        """
        if not self.featured_categories:
            return list(CATEGORY)

        valid_slugs = set(CATEGORY_LABELS.keys())
        return [
            (slug, CATEGORY_LABELS[slug])
            for slug in self.featured_categories
            if slug in valid_slugs
        ]


class AnalyticsEvent(models.Model):
    """A single recorded behavioral analytics event (PR-0e, G16/F-07).

    Lives in core (a leaf app every domain already depends on) rather than a
    new app, per the approved design decision — recording is a cross-domain
    concern (events, archive) and core is the existing shared-dependency
    leaf.

    Privacy: user is stored only as a pseudonymous, non-reversible
    ``user_key`` (see core.analytics.pseudonymous_user_key), never a direct
    FK to the user — this table intentionally cannot be joined back to
    accounts.User. ``context`` must never carry free text, contact info, or
    media URLs (enforced by core.analytics.record_event's forbidden-key
    guard, not by this model).
    """

    class EventName(models.TextChoices):
        EVENT_LIST_VIEWED = "event_list_viewed", "Event list viewed"
        EVENT_SEARCHED = "event_searched", "Event searched"
        EVENT_DETAIL_VIEWED = "event_detail_viewed", "Event detail viewed"
        EVENT_INTERESTED = "event_interested", "Event interested"
        EVENT_PLANNED = "event_planned", "Event planned"
        EVENT_MARKED_VISITED = "event_marked_visited", "Event marked visited"
        VISIT_RECORD_CREATED = "visit_record_created", "Visit record created"
        VISIT_PHOTO_ADDED = "visit_photo_added", "Visit photo added"

    event_name = models.CharField(max_length=32, choices=EventName.choices)
    # Pseudonymous per-user cohort key (see core.analytics), "" for an
    # anonymous/unauthenticated request — never a direct user reference.
    user_key = models.CharField(max_length=64, blank=True)
    # "" when the event has no single target (e.g. a list view).
    target_type = models.CharField(max_length=32, blank=True)
    target_id = models.BigIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    context = models.JSONField(default=dict, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["event_name", "created_at"]),
        ]
