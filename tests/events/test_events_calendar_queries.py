"""Events month-overlap query contract (dual-calendar Test List §단계 3:
CAL-3-01~02).

events.queries.list_published_events_for_month does not exist yet — the
whole file is expected to fail at collection with ImportError until it is
added (mirrors tests/archive/test_activity_log_entry.py's convention).

Overlap rule under test (service design §6): a published event is included
in a queried month when

    start_date <= 조회 월의 마지막 날
    그리고
    (effective_end := end_date if end_date is not None else start_date)
        >= 조회 월의 첫날

A null start_date always excludes an event from the calendar (it remains
reachable from the existing plain listing, service design §6). Non-published
events are always excluded.
"""
from datetime import date

import pytest

from events.models import Event
from events.queries import list_published_events_for_month


@pytest.mark.domain
@pytest.mark.django_db
@pytest.mark.parametrize(
    "start_date, end_date, publish_status, expected_included",
    [
        # 조회 월(2026-07) 안에서 완전히 겹친다.
        (date(2026, 7, 10), date(2026, 7, 20), Event.PublishStatus.PUBLISHED, True),
        # 다음 달에만 있어 전혀 겹치지 않는다.
        (date(2026, 8, 5), date(2026, 8, 10), Event.PublishStatus.PUBLISHED, False),
        # 시작일이 월의 마지막 날과 정확히 같고(경계, <= 포함) 종료일이 없어
        # 시작일 하루짜리로 취급된다(§6) — 그래도 포함되어야 한다.
        (date(2026, 7, 31), None, Event.PublishStatus.PUBLISHED, True),
        # 종료일이 월의 첫날과 정확히 같다(경계, >= 포함) — 시작일은 전달.
        (date(2026, 6, 25), date(2026, 7, 1), Event.PublishStatus.PUBLISHED, True),
        # 여러 달에 걸쳐 조회 월을 완전히 감싼다.
        (date(2026, 6, 1), date(2026, 9, 1), Event.PublishStatus.PUBLISHED, True),
        # 시작일이 없으면 기간이 겹치더라도 달력에서 제외된다.
        (None, date(2026, 7, 15), Event.PublishStatus.PUBLISHED, False),
        # 기간은 겹치지만 draft라 공개 달력에서 제외된다.
        (date(2026, 7, 10), date(2026, 7, 15), Event.PublishStatus.DRAFT, False),
    ],
    ids=[
        "겹치는_행사_포함",
        "겹치지_않는_행사_제외",
        "시작일_경계",
        "종료일_경계",
        "여러_달_걸침",
        "시작일_없음_제외",
        "draft_상태_제외",
    ],
)
def test_월_겹침_판정_규칙에_따라_행사_포함_여부가_결정된다(
    make_event, start_date, end_date, publish_status, expected_included
):
    event = make_event(
        title="겹침 판정 대상 행사",
        start_date=start_date,
        end_date=end_date,
        publish_status=publish_status,
    )

    qs = list_published_events_for_month({}, year=2026, month=7)
    ids = set(qs.values_list("id", flat=True))

    assert (event.id in ids) is expected_included


@pytest.mark.domain
@pytest.mark.django_db
@pytest.mark.parametrize(
    "filter_key, filter_value, matching_kwargs, non_matching_kwargs",
    [
        ("region", ["서울"], {"region": "서울"}, {"region": "부산"}),
        (
            "category",
            ["popup_store"],
            {"category": "popup_store"},
            {"category": "exhibition"},
        ),
    ],
    ids=["지역", "카테고리"],
)
def test_월_조회는_기존_필터와_결합해_적용된다(
    make_event, filter_key, filter_value, matching_kwargs, non_matching_kwargs
):
    matching = make_event(
        title="필터 일치 행사",
        start_date=date(2026, 7, 10),
        end_date=date(2026, 7, 12),
        **matching_kwargs,
    )
    non_matching = make_event(
        title="필터 불일치 행사",
        start_date=date(2026, 7, 10),
        end_date=date(2026, 7, 12),
        **non_matching_kwargs,
    )

    qs = list_published_events_for_month({filter_key: filter_value}, year=2026, month=7)
    ids = set(qs.values_list("id", flat=True))

    assert matching.id in ids
    assert non_matching.id not in ids
