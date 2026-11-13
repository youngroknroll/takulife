"""공개 화면이 같은 행사 조회를 짧은 시간 안에 되풀이하지 않게 프로세스
메모리에 잠시 담는다. 사용자별 상태·필터 있는 조회는 담지 않는다. 게시·
수정은 유지 시간이 지나야 반영된다.
"""

from django.conf import settings
from django.core.cache import caches

from events.queries import list_published_events_for_month

CACHE_ALIAS = "public"


def public_month_events(*, year, month, today):
    # 운영자가 0으로 캐시를 끄면 캐시 저장소를 아예 부르지 않는다(캐시 장애 때도 끌 수 있게).
    if settings.PUBLIC_CACHE_TTL_SECONDS == 0:
        return list(list_published_events_for_month({}, year=year, month=month, today=today))

    cache = caches[CACHE_ALIAS]
    # 진행 중·예정 구분이 오늘 날짜에 따라 달라지므로 날짜를 키에 넣는다.
    cache_key = f"public_month_events:{year:04d}-{month:02d}:{today.isoformat()}"
    events = cache.get(cache_key)
    if events is not None:
        return events

    events = list(list_published_events_for_month({}, year=year, month=month, today=today))
    cache.set(cache_key, events, timeout=settings.PUBLIC_CACHE_TTL_SECONDS)
    return events
