"""관리 명령 report_translation_queue(읽기 전용) 검증. 코치의 TR-33은
"--dry-run" 옵션이 있는 명령을 가정했지만(prompt_plan.md §10-5), 이 트랙의
실제 브리프는 인자 없는 읽기 전용 보고 명령으로 확정했다 — 이 파일은 그
확정 형태만 검증한다."""
import io

import pytest
from django.core.management import call_command

from events.models import Event
from events.content_translation import source_hash


pytestmark = [pytest.mark.django_db, pytest.mark.domain]


def _fields(title):
    return {
        "title": title,
        "work_title": "원작",
        "location_name": "코엑스",
        "summary": "요약",
    }


def _make_four_published_events(make_event):
    pending = make_event(**_fields("대기 중인 행사"))

    up_to_date_fields = _fields("최신 번역 행사")
    up_to_date = make_event(
        **up_to_date_fields,
        text_translations={
            "source_hash": source_hash(up_to_date_fields),
            "manual": False,
            "en": {"title": "Latest translated event", "work_title": "Work", "location_name": "Coex", "summary": "Summary"},
            "ja": None,
            "zh-hans": {"title": "最新翻译活动", "work_title": "作品", "location_name": "Coex", "summary": "摘要"},
        },
    )

    stale_fields = _fields("낡은_해시_행사")
    stale = make_event(
        **stale_fields,
        text_translations={
            "source_hash": "0" * 64,
            "manual": False,
            "en": {"title": "stale", "work_title": "stale", "location_name": "stale", "summary": "stale"},
            "ja": {"title": "stale", "work_title": "stale", "location_name": "stale", "summary": "stale"},
            "zh-hans": {"title": "stale", "work_title": "stale", "location_name": "stale", "summary": "stale"},
        },
    )

    manual = make_event(
        **_fields("수동_확정_행사"),
        text_translations={"source_hash": "irrelevant", "manual": True},
    )

    return pending, up_to_date, stale, manual


def _run_command():
    out = io.StringIO()
    call_command("report_translation_queue", stdout=out)
    lines = out.getvalue().splitlines()
    return dict(line.split("=", 1) for line in lines if line)


def test_구성된_게시_이벤트_4건에서_대기_최신_수동_격리_수치가_정확하다(make_event, make_draft_event):
    _make_four_published_events(make_event)
    make_draft_event(**_fields("초안 행사"))

    counts = _run_command()

    assert counts == {
        "published": "4",
        "pending": "2",
        "up_to_date": "1",
        "manual": "1",
        "quarantined_en": "0",
        "quarantined_ja": "1",
        "quarantined_zh-hans": "0",
    }


def test_명령은_아무것도_저장하지_않는다(make_event):
    pending, up_to_date, stale, manual = _make_four_published_events(make_event)
    before = {
        event.id: event.text_translations
        for event in [pending, up_to_date, stale, manual]
    }

    _run_command()

    for event_id, translations in before.items():
        event = Event.objects.get(pk=event_id)
        assert event.text_translations == translations


def test_게시_이벤트가_없으면_모두_0이다(make_draft_event):
    make_draft_event(**_fields("초안만 있는 상태"))

    counts = _run_command()

    assert counts == {
        "published": "0",
        "pending": "0",
        "up_to_date": "0",
        "manual": "0",
        "quarantined_en": "0",
        "quarantined_ja": "0",
        "quarantined_zh-hans": "0",
    }


def test_queue_report가_같은_수치를_딕셔너리로_돌려준다(make_event, make_draft_event):
    from events.translation_queue import queue_report

    _make_four_published_events(make_event)
    make_draft_event(**_fields("초안 행사"))

    report = queue_report()

    assert report == {
        "published": 4,
        "pending": 2,
        "up_to_date": 1,
        "manual": 1,
        "quarantined_en": 0,
        "quarantined_ja": 1,
        "quarantined_zh-hans": 0,
    }
