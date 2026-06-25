"""Tests for events/management/commands/seed_demo_events.py.

Covers:
- Running seed_demo_events creates exactly 5 published events.
- Running it twice is idempotent: still 5 events, no duplicates.
"""
import pytest
from django.core.management import call_command

from events.models import Event


@pytest.mark.django_db
class TestSeedDemoEvents:
    def test_creates_five_published_events(self):
        call_command("seed_demo_events", verbosity=0)
        assert Event.objects.published().count() == 5

    def test_idempotent_second_run_does_not_create_duplicates(self):
        call_command("seed_demo_events", verbosity=0)
        call_command("seed_demo_events", verbosity=0)
        assert Event.objects.published().count() == 5
