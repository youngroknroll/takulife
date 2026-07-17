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

pytestmark = pytest.mark.domain


@pytest.mark.django_db
class TestSeedDemoEvents:
    def test_데모_행사_시드_명령을_실행하면_16건_이상의_게시된_행사가_생성된다(self):
        call_command("seed_demo_events", verbosity=0)
        # Seed now creates more events to exceed hscroll thresholds
        assert Event.objects.published().count() >= 16

    def test_데모_행사_시드_명령을_두번_실행해도_중복_없이_같은_건수를_유지한다(self):
        call_command("seed_demo_events", verbosity=0)
        first_count = Event.objects.published().count()
        call_command("seed_demo_events", verbosity=0)
        assert Event.objects.published().count() == first_count

    def test_데모_행사_시드_후_마감_임박_기간_밖의_진행중_행사가_7건_이상이다(self):
        today = date.today()
        call_command("seed_demo_events", verbosity=0)
        # Ongoing: started <= today, ending > today+5 (not in closing window)
        ongoing_beyond_closing = Event.objects.published().filter(
            start_date__lte=today,
            end_date__gt=today + timedelta(days=5),
        ).count()
        assert ongoing_beyond_closing >= 7

    def test_데모_행사_시드_후_마감_임박_기간_내_행사가_4건_이상이다(self):
        today = date.today()
        call_command("seed_demo_events", verbosity=0)
        # Closing: started <= today, ending in [today, today+5]
        closing = Event.objects.published().filter(
            start_date__lte=today,
            end_date__gte=today,
            end_date__lte=today + timedelta(days=5),
        ).count()
        assert closing >= 4

    def test_데모_행사_시드_후_팬미팅_카테고리_행사가_존재한다(self):
        call_command("seed_demo_events", verbosity=0)
        assert Event.objects.published().filter(category="fan_meeting").exists()
