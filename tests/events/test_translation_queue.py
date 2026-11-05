"""번역 대기 큐 pending_events의 선정·배제·정렬 규칙 — DB가 필요한 도메인 테스트."""

import pytest

from events.content_translation import TRANSLATED_FIELDS, source_hash
from events.models import Event
from events.translation_queue import PENDING_LIMIT, pending_events

pytestmark = pytest.mark.domain


def _event_fields(event):
    return {name: getattr(event, name) for name in TRANSLATED_FIELDS}


@pytest.mark.django_db
def test_게시되지_않은_이벤트는_대기_목록에_없다(make_event, make_draft_event):
    published = make_event(title="게시된 행사")
    make_draft_event(title="초안 행사")

    result = pending_events()

    assert [item["event_id"] for item in result] == [published.id]


@pytest.mark.django_db
def test_번역이_없는_게시_이벤트는_대기_목록에_원문_필드와_해시와_함께_나온다(make_event):
    event = make_event(
        title="2026 도쿄 코믹마켓",
        work_title="원피스",
        location_name="도쿄 빅사이트",
        summary="10월 24일 개최",
    )

    result = pending_events()

    fields = _event_fields(event)
    assert result == [
        {
            "event_id": event.id,
            "source_hash": source_hash(fields),
            "fields": fields,
        }
    ]


@pytest.mark.django_db
def test_대기_목록은_20건을_넘지_않는다(make_event):
    for index in range(25):
        make_event(title=f"행사 {index}")

    assert PENDING_LIMIT == 20
    assert len(pending_events()) == 20
    assert len(pending_events(limit=5)) == 5


@pytest.mark.django_db
def test_한도가_0이면_빈_목록이다(make_event):
    make_event(title="번역 없는 게시 행사")

    assert pending_events(limit=0) == []


@pytest.mark.django_db
def test_대기_목록은_이벤트_id_오름차순이다(make_event):
    first = make_event(title="A")
    second = make_event(title="B")
    third = make_event(title="C")
    # 갱신 순서를 id 순서와 다르게 섞어, 정렬이 id 기준임을 구분한다.
    third.view_count = 1
    third.save()
    first.view_count = 5
    first.save()
    second.view_count = 50
    second.save()

    result = pending_events()

    assert [item["event_id"] for item in result] == [first.id, second.id, third.id]


@pytest.mark.django_db
def test_manual_이벤트는_대기_목록에서_빠진다(make_event):
    event = make_event(title="수동 번역 확정")
    event.text_translations = {"manual": True, "source_hash": "낡은-해시"}
    event.save()

    result = pending_events()

    assert [item["event_id"] for item in result] == []


@pytest.mark.django_db
def test_번역이_현재_해시로_저장된_이벤트는_대기_목록에서_빠진다(make_event):
    event = make_event(title="이미 번역됨")
    current_hash = source_hash(_event_fields(event))
    event.text_translations = {
        "source_hash": current_hash,
        "manual": False,
        "en": {"title": "Already translated", "work_title": "", "location_name": "", "summary": ""},
        "ja": None,
        "zh-hans": {"title": "已经翻译", "work_title": "", "location_name": "", "summary": ""},
    }
    event.save()

    result = pending_events()

    assert [item["event_id"] for item in result] == []


@pytest.mark.django_db
def test_격리된_언어가_있어도_해시가_같으면_대기_목록에_다시_오르지_않는다(make_event):
    event = make_event(title="세 언어 모두 격리")
    current_hash = source_hash(_event_fields(event))
    event.text_translations = {
        "source_hash": current_hash,
        "manual": False,
        "en": None,
        "ja": None,
        "zh-hans": None,
    }
    event.save()

    result = pending_events()

    assert [item["event_id"] for item in result] == []


@pytest.mark.django_db
def test_원문이_바뀌면_번역된_이벤트가_다시_대기_목록에_나온다(make_event):
    event = make_event(title="바뀌기 전 제목")
    old_hash = source_hash(_event_fields(event))
    event.text_translations = {
        "source_hash": old_hash,
        "manual": False,
        "en": {"title": "Before change", "work_title": "", "location_name": "", "summary": ""},
        "ja": None,
        "zh-hans": None,
    }
    event.save()

    event.title = "바뀐 뒤 제목"
    event.save()
    new_hash = source_hash(_event_fields(event))

    result = pending_events()

    assert [item["event_id"] for item in result] == [event.id]
    assert result[0]["source_hash"] == new_hash
    assert new_hash != old_hash


@pytest.mark.django_db
def test_엔트리의_해시가_낡은_이벤트는_번역이_있어도_대기_목록에_나온다(make_event):
    event = make_event(title="낡은 해시로 저장됨")
    event.text_translations = {
        "source_hash": "낡은-해시-문자열",
        "manual": False,
        "en": {"title": "Stale hash entry", "work_title": "", "location_name": "", "summary": ""},
        "ja": None,
        "zh-hans": None,
    }
    event.save()

    result = pending_events()

    assert [item["event_id"] for item in result] == [event.id]


@pytest.mark.django_db
def test_저장값이_dict가_아니어도_대기_목록이_깨지지_않는다(make_event):
    event = make_event(title="손상된 저장값")
    Event.objects.filter(pk=event.pk).update(text_translations=[])

    result = pending_events()

    assert [item["event_id"] for item in result] == [event.id]
