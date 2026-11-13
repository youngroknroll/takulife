"""공개 화면 캐시(web/public_cache.py)의 유지 시간·키·격리 계약을 지킨다.

public_month_events는 아직 존재하지 않아, 추가되기 전까지는 이 파일 전체가
수집 단계에서 ModuleNotFoundError로 실패하는 것이 정상이다.
"""

from datetime import date
import time as real_time

from django.core.cache import caches
import django.core.cache.backends.base as cache_base
import django.core.cache.backends.locmem as cache_locmem
import pytest

import web.public_cache as public_cache_module
from web.public_cache import public_month_events


class _FakeClock:
    """`time` 모듈을 대신하는, 제어 가능한 가짜 시계."""

    def __init__(self, start):
        self._now = start

    def time(self):
        return self._now

    def advance(self, seconds):
        self._now += seconds


@pytest.fixture
def public_cache_locmem(settings, monkeypatch):
    """공개 캐시는 테스트 설정에서 꺼져 있어(DummyCache) 이 픽스처를 요청한
    테스트만 켠다. 유지 시간 계산(base.py)과 만료 판정(locmem.py)이 서로
    다른 모듈에서 시간을 읽어 두 곳을 같은 가짜 시계로 바꾼다.
    """
    settings.CACHES = {
        **settings.CACHES,
        "public": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "test-public-cache",
            "OPTIONS": {"MAX_ENTRIES": 200},
        },
    }
    clock = _FakeClock(real_time.time())
    monkeypatch.setattr(cache_base, "time", clock)
    monkeypatch.setattr(cache_locmem, "time", clock)

    caches["public"].clear()
    yield clock
    caches["public"].clear()


@pytest.mark.domain
@pytest.mark.django_db
def test_캐시_유효_시간_안에_같은_달을_다시_조회하면_변경_전_행사_목록을_그대로_돌려준다(
    make_event, public_cache_locmem, django_assert_num_queries
):
    make_event(title="초기행사", start_date=date(2026, 6, 1), end_date=date(2026, 6, 1))

    public_month_events(year=2026, month=6, today=date(2026, 6, 1))

    make_event(title="추가행사", start_date=date(2026, 6, 10), end_date=date(2026, 6, 10))
    public_cache_locmem.advance(59)

    with django_assert_num_queries(0):
        events = public_month_events(year=2026, month=6, today=date(2026, 6, 1))

    assert [event.title for event in events] == ["초기행사"]


@pytest.mark.domain
@pytest.mark.django_db
def test_캐시_유효_시간이_지나_같은_달을_다시_조회하면_새로_반영된_행사_목록을_돌려준다(
    make_event, public_cache_locmem, django_assert_num_queries
):
    make_event(title="초기행사", start_date=date(2026, 6, 1), end_date=date(2026, 6, 1))
    public_month_events(year=2026, month=6, today=date(2026, 6, 1))

    make_event(title="추가행사", start_date=date(2026, 6, 10), end_date=date(2026, 6, 10))
    public_cache_locmem.advance(61)

    with django_assert_num_queries(1):
        events = public_month_events(year=2026, month=6, today=date(2026, 6, 1))

    assert sorted(event.title for event in events) == ["초기행사", "추가행사"]


@pytest.mark.domain
@pytest.mark.django_db
def test_공개_캐시_유효_시간이_0이면_캐시를_거치지_않고_매번_새로_조회한다(
    make_event, public_cache_locmem, settings, monkeypatch
):
    settings.PUBLIC_CACHE_TTL_SECONDS = 0
    make_event(title="초기행사", start_date=date(2026, 6, 1), end_date=date(2026, 6, 1))

    # 캐시를 끄는 값이 캐시 장애 때도 듣는지 보려고 저장소를 일부러 고장 낸다.
    def _raise_cache_failure(*args, **kwargs):
        raise RuntimeError("공개 캐시 장애 주입")

    monkeypatch.setattr(caches["public"], "get", _raise_cache_failure)
    monkeypatch.setattr(caches["public"], "set", _raise_cache_failure)

    public_month_events(year=2026, month=6, today=date(2026, 6, 1))
    make_event(title="추가행사", start_date=date(2026, 6, 10), end_date=date(2026, 6, 10))

    events = public_month_events(year=2026, month=6, today=date(2026, 6, 1))

    assert sorted(event.title for event in events) == ["초기행사", "추가행사"]


@pytest.mark.domain
@pytest.mark.django_db
def test_로컬_날짜가_다르면_같은_달_조회도_서로_다른_캐시_값을_가진다(
    make_event, public_cache_locmem, django_assert_num_queries
):
    make_event(title="초기행사", start_date=date(2026, 6, 1), end_date=date(2026, 6, 1))
    public_month_events(year=2026, month=6, today=date(2026, 6, 1))

    make_event(title="추가행사", start_date=date(2026, 6, 10), end_date=date(2026, 6, 10))

    with django_assert_num_queries(1):
        events = public_month_events(year=2026, month=6, today=date(2026, 6, 2))

    assert sorted(event.title for event in events) == ["초기행사", "추가행사"]


@pytest.mark.domain
@pytest.mark.django_db
def test_달이_다르면_공개_월별_조회는_서로_다른_캐시_값을_가진다(
    make_event, public_cache_locmem, django_assert_num_queries
):
    make_event(title="6월행사", start_date=date(2026, 6, 1), end_date=date(2026, 6, 1))
    make_event(title="7월행사", start_date=date(2026, 7, 1), end_date=date(2026, 7, 1))
    public_month_events(year=2026, month=6, today=date(2026, 6, 1))

    with django_assert_num_queries(1):
        events = public_month_events(year=2026, month=7, today=date(2026, 6, 1))

    assert [event.title for event in events] == ["7월행사"]


@pytest.mark.domain
@pytest.mark.django_db
def test_월별_조회가_실패하면_캐시에_남지_않아_다음_호출이_다시_조회한다(
    make_event, public_cache_locmem, django_assert_num_queries, monkeypatch
):
    make_event(title="초기행사", start_date=date(2026, 6, 1), end_date=date(2026, 6, 1))

    real_query = public_cache_module.list_published_events_for_month

    def _raise(*args, **kwargs):
        raise RuntimeError("월 조회 실패 주입")

    monkeypatch.setattr(public_cache_module, "list_published_events_for_month", _raise)

    with pytest.raises(RuntimeError):
        public_month_events(year=2026, month=6, today=date(2026, 6, 1))

    monkeypatch.setattr(public_cache_module, "list_published_events_for_month", real_query)

    with django_assert_num_queries(1):
        events = public_month_events(year=2026, month=6, today=date(2026, 6, 1))

    assert [event.title for event in events] == ["초기행사"]
