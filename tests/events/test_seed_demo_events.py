"""events/management/commands/seed_demo_events.py를 검증한다.

다루는 범위:
- seed_demo_events 실행 시 기대한 건수만큼 게시 행사가 생성된다.
- 두 번 실행해도 멱등하다: 같은 건수, 중복 없음.
- 시드 후: 진행중 >= 7, 마감임박(<=D+5) >= 4, fan_meeting 행사 존재.
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
        # 가로 스크롤 노출 기준을 넘기도록 시드가 더 많은 행사를 만든다.
        assert Event.objects.published().count() >= 16

    def test_데모_행사_시드_명령을_두번_실행해도_중복_없이_같은_건수를_유지한다(self):
        call_command("seed_demo_events", verbosity=0)
        first_count = Event.objects.published().count()
        call_command("seed_demo_events", verbosity=0)
        assert Event.objects.published().count() == first_count

    def test_데모_행사_시드_후_마감_임박_기간_밖의_진행중_행사가_7건_이상이다(self):
        today = date.today()
        call_command("seed_demo_events", verbosity=0)
        # 진행중: 시작 <= 오늘, 종료 > 오늘+5(마감임박 창 밖)
        ongoing_beyond_closing = Event.objects.published().filter(
            start_date__lte=today,
            end_date__gt=today + timedelta(days=5),
        ).count()
        assert ongoing_beyond_closing >= 7

    def test_데모_행사_시드_후_마감_임박_기간_내_행사가_4건_이상이다(self):
        today = date.today()
        call_command("seed_demo_events", verbosity=0)
        # 마감임박: 시작 <= 오늘, 종료가 [오늘, 오늘+5] 구간
        closing = Event.objects.published().filter(
            start_date__lte=today,
            end_date__gte=today,
            end_date__lte=today + timedelta(days=5),
        ).count()
        assert closing >= 4

    def test_데모_행사_시드_후_팬미팅_카테고리_행사가_존재한다(self):
        call_command("seed_demo_events", verbosity=0)
        assert Event.objects.published().filter(category="fan_meeting").exists()
