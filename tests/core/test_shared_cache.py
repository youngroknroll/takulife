"""Shared cache (PR-0e checkpoint A2): DatabaseCache table provisioning.

(.docs/plans/2026-07-14-stage0-deployment-foundation-plan.md §8 PR-0e)

Django's test runner auto-creates DatabaseCache tables for the *test*
database (django/db/backends/base/creation.py), so this test alone cannot
prove the production/dev database gets the "django_cache" table — that is
what the core migration (RunPython createcachetable) is for. This test
still guards the cache round trip through the real ORM/DB connection so a
future backend change that breaks it is caught.
"""
import pytest
from django.core.cache import cache


@pytest.mark.django_db
def test_cache_set_and_get_round_trip_after_migrate():
    cache.set("pr-0e-shared-cache-key", "shared-value", timeout=60)

    assert cache.get("pr-0e-shared-cache-key") == "shared-value"
