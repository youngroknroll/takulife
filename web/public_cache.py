"""공개 화면이 같은 행사 조회를 짧은 시간 안에 되풀이하지 않게 프로세스
메모리에 잠시 담는다. 사용자별 상태·필터 있는 조회는 담지 않는다. 게시·
수정은 유지 시간이 지나야 반영된다.
"""

import logging

from django.conf import settings
from django.core.cache import caches
from django.db.models import Count

from core.models import HomeConfig
from events.models import Event
from events.queries import (
    consumer_category_choices,
    list_published_events,
    list_published_events_for_month,
)

CACHE_ALIAS = "public"

logger = logging.getLogger(__name__)


def _cached(cache_key, load):
    """담아 둔 값이 있으면 돌려주고, 없으면 `load()`로 읽어 유지 시간 동안
    담는다. 유지 시간이 0이면 저장소를 아예 부르지 않는다(캐시 장애 때도
    끌 수 있게). 캐시 저장소가 고장 나면 기록을 남기고 DB에서 읽은 값을
    그대로 쓴다."""
    if settings.PUBLIC_CACHE_TTL_SECONDS == 0:
        return load()

    cache = caches[CACHE_ALIAS]
    try:
        value = cache.get(cache_key)
    except Exception:
        logger.exception("Public cache read failed for key=%s", cache_key)
        value = None
    if value is not None:
        return value

    value = load()
    try:
        cache.set(cache_key, value, timeout=settings.PUBLIC_CACHE_TTL_SECONDS)
    except Exception:
        logger.exception("Public cache write failed for key=%s", cache_key)
    return value


def public_month_events(*, year, month, today):
    # 진행 중·예정 구분이 오늘 날짜에 따라 달라지므로 날짜를 키에 넣는다.
    cache_key = f"public_month_events:{year:04d}-{month:02d}:{today.isoformat()}"
    return _cached(
        cache_key,
        lambda: list(list_published_events_for_month({}, year=year, month=month, today=today)),
    )


def _load_home_public_sections(*, today):
    return {
        "ongoing_rows": list(list_published_events({"status": "ongoing"}, today=today)[:15]),
        "closing_rows": list(Event.objects.published().ending_within_days(5, today=today)[:15]),
        # 슬라이더는 기간이 이미 끝난 행사(end_date < today)를 제외한다.
        # end_date가 없는 행사는 "종료"가 될 수 없으므로 그대로 남긴다.
        "recent_rows": list(
            Event.objects.published().exclude(end_date__lt=today).order_by("-id")[:15]
        ),
        # 홈 대표 행사: 인기(조회수) 슬라이더 대신 공개 목록 기본 우선순위
        # (진행중 -> 예정 -> 종료, "active"는 종료 행사를 제외)의 최대 5건을
        # 로테이터로 노출한다.
        "featured_event_rows": list(list_published_events({"status": "active"}, today=today)[:5]),
        # "카테고리로 둘러보기" 집계: HomeConfig로 스태프가 순서/선택을
        # 큐레이션한 카테고리와 게시 건수를 함께 담는다.
        "category_counts": {
            row["category"]: row["count"]
            for row in Event.objects.published().values("category").annotate(count=Count("id"))
        },
        "featured_category_pairs": list(HomeConfig.get_solo().featured_category_pairs()),
    }


def home_public_sections(*, today):
    """홈의 공개 섹션을 날짜별로 담는다. 사용자별 상태와 로그인 사용자의
    예정 구간은 담지 않는다."""
    cache_key = f"home_public_sections:{today.isoformat()}"
    return _cached(cache_key, lambda: _load_home_public_sections(today=today))


def public_category_choices():
    """행사 필터의 카테고리 (slug, 원문 라벨) 목록을 담는다. 번역은 화면이
    요청마다 한다."""
    return _cached("public_category_choices", consumer_category_choices)
