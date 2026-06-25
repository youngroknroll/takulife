"""Management command: seed_demo_events

Creates 5 published demo events idempotently, using distinct categories and
varied view_count values so the popular-events deck ordering is visible.

Idempotency key: official_url (unique field on Event). A second run leaves
existing rows untouched and creates no new rows.
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from events.models import Event

_TODAY = date.today


def _demo_events():
    today = _TODAY()
    return [
        {
            "official_url": "https://demo.takulife.example/popup-1",
            "title": "[데모] 봄 팝업스토어",
            "category": "popup_store",
            "region": "seoul",
            "start_date": today - timedelta(days=5),
            "end_date": today + timedelta(days=10),
            "summary": "데모용 팝업스토어 행사입니다.",
            "view_count": 50,
            "publish_status": Event.PublishStatus.PUBLISHED,
        },
        {
            "official_url": "https://demo.takulife.example/collab-cafe-1",
            "title": "[데모] 애니메이션 콜라보 카페",
            "category": "collaboration_cafe",
            "region": "osaka",
            "start_date": today - timedelta(days=2),
            "end_date": today + timedelta(days=20),
            "summary": "데모용 콜라보 카페 행사입니다.",
            "view_count": 40,
            "publish_status": Event.PublishStatus.PUBLISHED,
        },
        {
            "official_url": "https://demo.takulife.example/theater-1",
            "title": "[데모] 극장 상영 특전",
            "category": "theater_bonus",
            "region": "tokyo",
            "start_date": today + timedelta(days=3),
            "end_date": today + timedelta(days=30),
            "summary": "데모용 극장 특전 행사입니다.",
            "view_count": 30,
            "publish_status": Event.PublishStatus.PUBLISHED,
        },
        {
            "official_url": "https://demo.takulife.example/goods-1",
            "title": "[데모] 한정 굿즈 예약",
            "category": "goods_reservation",
            "region": "busan",
            "start_date": today - timedelta(days=10),
            "end_date": today + timedelta(days=5),
            "summary": "데모용 굿즈 예약 행사입니다.",
            "view_count": 20,
            "publish_status": Event.PublishStatus.PUBLISHED,
        },
        {
            "official_url": "https://demo.takulife.example/exhibition-1",
            "title": "[데모] 아트 전시회",
            "category": "exhibition",
            "region": "seoul",
            "start_date": today,
            "end_date": today + timedelta(days=15),
            "summary": "데모용 전시회 행사입니다.",
            "view_count": 10,
            "publish_status": Event.PublishStatus.PUBLISHED,
        },
    ]


class Command(BaseCommand):
    help = "Seed 5 published demo events for the popular-events deck (idempotent)."

    def handle(self, *args, **options):
        created_count = 0
        skipped_count = 0

        for spec in _demo_events():
            official_url = spec["official_url"]
            defaults = {k: v for k, v in spec.items() if k != "official_url"}
            _, created = Event.objects.get_or_create(
                official_url=official_url,
                defaults=defaults,
            )
            if created:
                created_count += 1
            else:
                skipped_count += 1

        self.stdout.write(
            f"seed_demo_events: created={created_count}, skipped={skipped_count}"
        )
