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
