"""데모 이벤트 21개를 게시 상태로 멱등하게 생성한다.

카테고리와 view_count를 다양하게 둬서 인기 이벤트 정렬이 눈에 보이게 한다.
멱등 키는 official_url이라 재실행해도 기존 행은 그대로 두고 새로 만들지 않는다.
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand

from events.models import Event

_TODAY = date.today


def _demo_events():
    today = _TODAY()
    return [
        # --- 기본 5개 이벤트 ---
        {
            "official_url": "https://demo.takulife.example/popup-1",
            "title": "[데모] 봄 팝업스토어",
            "category": "popup_store",
            "region": "seoul",
            "start_date": today - timedelta(days=5),
            "end_date": today + timedelta(days=10),
            "summary": "데모용 팝업스토어 이벤트입니다.",
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
            "summary": "데모용 콜라보 카페 이벤트입니다.",
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
            "summary": "데모용 극장 특전 이벤트입니다.",
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
            "summary": "데모용 굿즈 예약 이벤트입니다.",
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
            "summary": "데모용 전시회 이벤트입니다.",
            "view_count": 10,
            "publish_status": Event.PublishStatus.PUBLISHED,
        },
        # --- 진행중 이벤트(종료일이 today+5 이후, 마감임박 아님) ---
        {
            "official_url": "https://demo.takulife.example/popup-2",
            "title": "[데모] 여름 팝업스토어",
            "category": "popup_store",
            "region": "gyeonggi",
            "start_date": today - timedelta(days=3),
            "end_date": today + timedelta(days=14),
            "summary": "데모용 여름 팝업스토어 이벤트입니다.",
            "view_count": 45,
            "publish_status": Event.PublishStatus.PUBLISHED,
        },
        {
            "official_url": "https://demo.takulife.example/collab-cafe-2",
            "title": "[데모] 게임 콜라보 카페",
            "category": "collaboration_cafe",
            "region": "incheon",
            "start_date": today - timedelta(days=1),
            "end_date": today + timedelta(days=21),
            "summary": "데모용 게임 콜라보 카페 이벤트입니다.",
            "view_count": 35,
            "publish_status": Event.PublishStatus.PUBLISHED,
        },
        {
            "official_url": "https://demo.takulife.example/exhibition-2",
            "title": "[데모] 일러스트 전시회",
            "category": "exhibition",
            "region": "busan",
            "start_date": today - timedelta(days=4),
            "end_date": today + timedelta(days=28),
            "summary": "데모용 일러스트 전시회 이벤트입니다.",
            "view_count": 25,
            "publish_status": Event.PublishStatus.PUBLISHED,
        },
        {
            "official_url": "https://demo.takulife.example/popup-3",
            "title": "[데모] 한정판 팝업스토어",
            "category": "popup_store",
            "region": "seoul",
            "start_date": today - timedelta(days=2),
            "end_date": today + timedelta(days=30),
            "summary": "데모용 한정판 팝업스토어 이벤트입니다.",
            "view_count": 60,
            "publish_status": Event.PublishStatus.PUBLISHED,
        },
        {
            "official_url": "https://demo.takulife.example/goods-2",
            "title": "[데모] 콜라보 굿즈 예약",
            "category": "goods_reservation",
            "region": "online",
            "start_date": today - timedelta(days=1),
            "end_date": today + timedelta(days=25),
            "summary": "데모용 콜라보 굿즈 예약 이벤트입니다.",
            "view_count": 15,
            "publish_status": Event.PublishStatus.PUBLISHED,
        },
        {
            "official_url": "https://demo.takulife.example/exhibition-3",
            "title": "[데모] 피규어 전시회",
            "category": "exhibition",
            "region": "seoul",
            "start_date": today - timedelta(days=6),
            "end_date": today + timedelta(days=18),
            "summary": "데모용 피규어 전시회 이벤트입니다.",
            "view_count": 8,
            "publish_status": Event.PublishStatus.PUBLISHED,
        },
        {
            "official_url": "https://demo.takulife.example/popup-4",
            "title": "[데모] 시즌 팝업스토어",
            "category": "popup_store",
            "region": "gyeonggi",
            "start_date": today - timedelta(days=3),
            "end_date": today + timedelta(days=12),
            "summary": "데모용 시즌 팝업스토어 이벤트입니다.",
            "view_count": 55,
            "publish_status": Event.PublishStatus.PUBLISHED,
        },
        # --- 마감임박 이벤트(종료일이 today+1~today+5 사이) ---
        {
            "official_url": "https://demo.takulife.example/closing-d1",
            "title": "[데모] 마감 임박 D+1 전시",
            "category": "exhibition",
            "region": "seoul",
            "start_date": today - timedelta(days=7),
            "end_date": today + timedelta(days=1),
            "summary": "데모용 D+1 마감 전시 이벤트입니다.",
            "view_count": 70,
            "publish_status": Event.PublishStatus.PUBLISHED,
        },
        {
            "official_url": "https://demo.takulife.example/closing-d2",
            "title": "[데모] 마감 임박 D+2 팝업",
            "category": "popup_store",
            "region": "busan",
            "start_date": today - timedelta(days=5),
            "end_date": today + timedelta(days=2),
            "summary": "데모용 D+2 마감 팝업스토어 이벤트입니다.",
            "view_count": 65,
            "publish_status": Event.PublishStatus.PUBLISHED,
        },
        {
            "official_url": "https://demo.takulife.example/closing-d3",
            "title": "[데모] 마감 임박 D+3 카페",
            "category": "collaboration_cafe",
            "region": "gyeonggi",
            "start_date": today - timedelta(days=4),
            "end_date": today + timedelta(days=3),
            "summary": "데모용 D+3 마감 콜라보 카페 이벤트입니다.",
            "view_count": 58,
            "publish_status": Event.PublishStatus.PUBLISHED,
        },
        {
            "official_url": "https://demo.takulife.example/closing-d5",
            "title": "[데모] 마감 임박 D+5 굿즈",
            "category": "goods_reservation",
            "region": "online",
            "start_date": today - timedelta(days=3),
            "end_date": today + timedelta(days=5),
            "summary": "데모용 D+5 마감 굿즈 예약 이벤트입니다.",
            "view_count": 48,
            "publish_status": Event.PublishStatus.PUBLISHED,
        },
        # --- fan_meeting 카테고리(게시 1건, 진행중) ---
        {
            "official_url": "https://demo.takulife.example/fan-meeting-1",
            "title": "[데모] 아이돌 팬미팅",
            "category": "fan_meeting",
            "region": "seoul",
            "start_date": today - timedelta(days=2),
            "end_date": today + timedelta(days=20),
            "summary": "데모용 팬미팅 이벤트입니다.",
            "view_count": 80,
            "publish_status": Event.PublishStatus.PUBLISHED,
        },
    ]


class Command(BaseCommand):
    help = "Seed 21 published demo events for hscroll threshold verification (idempotent)."

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
