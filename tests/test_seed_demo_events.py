"""Tests for events/management/commands/seed_demo_events.py.

Covers:
- Running seed_demo_events creates the expected number of published events.
- Running it twice is idempotent: same count, no duplicates.
- After seeding: ongoing >= 7, closing(<=D+5) >= 4, fan_meeting event exists.
"""
import pytest
from datetime import date, timedelta

from django.core.management import call_command

from events.models import Event


@pytest.mark.django_db
class TestSeedDemoEvents:
    def test_creates_expected_published_events(self):
        call_command("seed_demo_events", verbosity=0)
        # Seed now creates more events to exceed hscroll thresholds
        assert Event.objects.published().count() >= 16

    def test_idempotent_second_run_does_not_create_duplicates(self):
        call_command("seed_demo_events", verbosity=0)
        first_count = Event.objects.published().count()
        call_command("seed_demo_events", verbosity=0)
        assert Event.objects.published().count() == first_count

    def test_ongoing_count_at_least_7_after_seed(self):
        today = date.today()
        call_command("seed_demo_events", verbosity=0)
        # Ongoing: started <= today, ending > today+5 (not in closing window)
        ongoing_beyond_closing = Event.objects.published().filter(
            start_date__lte=today,
            end_date__gt=today + timedelta(days=5),
        ).count()
        assert ongoing_beyond_closing >= 7

    def test_closing_count_at_least_4_after_seed(self):
        today = date.today()
        call_command("seed_demo_events", verbosity=0)
        # Closing: started <= today, ending in [today, today+5]
        closing = Event.objects.published().filter(
            start_date__lte=today,
            end_date__gte=today,
            end_date__lte=today + timedelta(days=5),
        ).count()
        assert closing >= 4

    def test_fan_meeting_event_exists_after_seed(self):
        call_command("seed_demo_events", verbosity=0)
        assert Event.objects.published().filter(category="fan_meeting").exists()
