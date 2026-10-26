"""번역 제출 서비스 submit_translation의 저장·거부·격리·로그 규칙 — 도메인 테스트.

events/translation_queue.py 없음(트랙 44-1 묶음 ④ 구현 전) → 전부 ImportError로 Red.
"""
import logging
import unicodedata

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from events.content_translation import TRANSLATED_FIELDS, source_hash
from events.models import Event

pytestmark = pytest.mark.domain

_SOURCE_FIELDS = {
    "title": "2026 도쿄 코믹마켓",
    "work_title": "원피스",
    "location_name": "도쿄 빅사이트",
    "summary": "10월 24일 개최",
}

_GOOD_TRANSLATIONS = {
    "en": {
        "title": "2026 Tokyo Comic Market",
        "work_title": "One Piece",
        "location_name": "Tokyo Big Sight",
        "summary": "Held on October 24",
    },
    "ja": {
        "title": "2026 東京コミックマーケット",
        "work_title": "ワンピース",
        "location_name": "東京ビッグサイト",
        "summary": "10月24日開催",
    },
    "zh-hans": {
        "title": "2026 东京漫展",
        "work_title": "海贼王",
        "location_name": "东京国际展览中心",
        "summary": "10月24日举办",
    },
}


def _make_source_event(make_event, **overrides):
    return make_event(**{**_SOURCE_FIELDS, **overrides})


def _event_fields(event):
    return {name: getattr(event, name) for name in TRANSLATED_FIELDS}


def _deep_copy_translations(translations):
    return {language: dict(fields) for language, fields in translations.items()}


@pytest.mark.django_db
def test_정상_제출은_세_언어를_저장하고_saved_상태를_돌려준다(make_event):
    event = _make_source_event(make_event)
    submitted_hash = source_hash(_event_fields(event))

    from events.translation_queue import submit_translation

    outcome = submit_translation(
        event_id=event.id,
        source_hash=submitted_hash,
        translations=_GOOD_TRANSLATIONS,
    )

    assert outcome.status == "saved"
    assert outcome.saved == ["en", "ja", "zh-hans"]
    assert outcome.quarantined == {}

    event.refresh_from_db()
    assert event.text_translations == {
        "source_hash": submitted_hash,
        "manual": False,
        "en": _GOOD_TRANSLATIONS["en"],
        "ja": _GOOD_TRANSLATIONS["ja"],
        "zh-hans": _GOOD_TRANSLATIONS["zh-hans"],
    }


@pytest.mark.django_db
def test_빈_원문_필드는_빈_문자열_번역으로_저장된다(make_event):
    event = _make_source_event(make_event, work_title="")
    translations = _deep_copy_translations(_GOOD_TRANSLATIONS)
    for language in translations:
        translations[language]["work_title"] = ""
    submitted_hash = source_hash(_event_fields(event))

    from events.translation_queue import submit_translation

    submit_translation(event_id=event.id, source_hash=submitted_hash, translations=translations)

    event.refresh_from_db()
    assert event.text_translations["en"]["work_title"] == ""


@pytest.mark.django_db
def test_격리된_언어는_null로_저장되고_나머지는_저장된다(make_event):
    event = _make_source_event(make_event)
    translations = _deep_copy_translations(_GOOD_TRANSLATIONS)
    translations["ja"]["title"] = "2026 도쿄 コミックマーケット"
    submitted_hash = source_hash(_event_fields(event))

    from events.translation_queue import submit_translation

    outcome = submit_translation(event_id=event.id, source_hash=submitted_hash, translations=translations)

    assert outcome.saved == ["en", "zh-hans"]
    assert outcome.quarantined == {"ja": "hangul_residue"}

    event.refresh_from_db()
    assert event.text_translations["ja"] is None
    assert isinstance(event.text_translations["en"], dict)
    assert isinstance(event.text_translations["zh-hans"], dict)


@pytest.mark.django_db
def test_세_언어가_모두_격리돼도_엔트리는_저장된다(make_event):
    event = _make_source_event(make_event)
    translations = _deep_copy_translations(_GOOD_TRANSLATIONS)
    for language in translations:
        translations[language]["title"] = _SOURCE_FIELDS["title"]
    submitted_hash = source_hash(_event_fields(event))

    from events.translation_queue import submit_translation

    outcome = submit_translation(event_id=event.id, source_hash=submitted_hash, translations=translations)

    assert outcome.status == "saved"
    assert outcome.saved == []

    event.refresh_from_db()
    assert event.text_translations["en"] is None
    assert event.text_translations["ja"] is None
    assert event.text_translations["zh-hans"] is None
    assert event.text_translations["source_hash"] == submitted_hash


@pytest.mark.django_db
def test_저장되는_번역은_NFC로_정규화된다(make_event):
    event = _make_source_event(make_event)
    translations = _deep_copy_translations(_GOOD_TRANSLATIONS)
    decomposed_title = "2026 Cafe" + chr(0x301) + " Fair"
    translations["en"]["title"] = decomposed_title
    submitted_hash = source_hash(_event_fields(event))

    from events.translation_queue import submit_translation

    submit_translation(event_id=event.id, source_hash=submitted_hash, translations=translations)

    event.refresh_from_db()
    assert event.text_translations["en"]["title"] == unicodedata.normalize("NFC", decomposed_title)


@pytest.mark.django_db
def test_manual_이벤트에_제출하면_거부되고_덮어쓰지_않는다(make_event):
    event = _make_source_event(make_event)
    locked_state = {
        "manual": True,
        "source_hash": "임의-해시",
        "en": {
            "title": "Staff edited title",
            "work_title": "Staff edited work",
            "location_name": "Staff edited location",
            "summary": "Staff edited summary",
        },
        "ja": None,
        "zh-hans": None,
    }
    event.text_translations = locked_state
    event.save()
    submitted_hash = source_hash(_event_fields(event))

    from events.content_translation import SubmissionRejected
    from events.translation_queue import submit_translation

    with pytest.raises(SubmissionRejected) as exc_info:
        submit_translation(event_id=event.id, source_hash=submitted_hash, translations=_GOOD_TRANSLATIONS)

    assert exc_info.value.code == "manual_locked"

    event.refresh_from_db()
    assert event.text_translations == locked_state


@pytest.mark.django_db
def test_없는_이벤트에_제출하면_거부된다():
    from events.content_translation import SubmissionRejected
    from events.translation_queue import submit_translation

    with pytest.raises(SubmissionRejected) as exc_info:
        submit_translation(event_id=999999, source_hash="아무해시", translations=_GOOD_TRANSLATIONS)

    assert exc_info.value.code == "not_found"


@pytest.mark.django_db
def test_게시되지_않은_이벤트에_제출하면_거부된다(make_draft_event):
    event = make_draft_event(**_SOURCE_FIELDS)
    submitted_hash = source_hash(_event_fields(event))

    from events.content_translation import SubmissionRejected
    from events.translation_queue import submit_translation

    with pytest.raises(SubmissionRejected) as exc_info:
        submit_translation(event_id=event.id, source_hash=submitted_hash, translations=_GOOD_TRANSLATIONS)

    assert exc_info.value.code == "not_found"


@pytest.mark.django_db
def test_해시가_낡았으면_거부되고_아무것도_저장하지_않는다(make_event):
    event = _make_source_event(make_event)
    stale_hash = source_hash(_event_fields(event))
    event.title = "원문이 바뀐 뒤"
    event.save()

    from events.content_translation import SubmissionRejected
    from events.translation_queue import submit_translation

    with pytest.raises(SubmissionRejected) as exc_info:
        submit_translation(event_id=event.id, source_hash=stale_hash, translations=_GOOD_TRANSLATIONS)

    assert exc_info.value.code == "stale_source"

    event.refresh_from_db()
    assert event.text_translations == {}


@pytest.mark.django_db
def test_구조가_틀린_제출은_스키마_사유로_거부된다(make_event):
    event = _make_source_event(make_event)
    submitted_hash = source_hash(_event_fields(event))
    broken_translations = _deep_copy_translations(_GOOD_TRANSLATIONS)
    del broken_translations["ja"]

    from events.content_translation import SubmissionRejected
    from events.translation_queue import submit_translation

    with pytest.raises(SubmissionRejected) as exc_info:
        submit_translation(event_id=event.id, source_hash=submitted_hash, translations=broken_translations)

    assert exc_info.value.code == "schema"
    event.refresh_from_db()
    assert event.text_translations == {}


@pytest.mark.django_db
def test_NUL_문자가_포함된_제출은_거부된다(make_event):
    event = _make_source_event(make_event)
    submitted_hash = source_hash(_event_fields(event))
    translations = _deep_copy_translations(_GOOD_TRANSLATIONS)
    translations["en"]["title"] = translations["en"]["title"] + chr(0)

    from events.content_translation import SubmissionRejected
    from events.translation_queue import submit_translation

    with pytest.raises(SubmissionRejected) as exc_info:
        submit_translation(event_id=event.id, source_hash=submitted_hash, translations=translations)

    assert exc_info.value.code == "nul"
    event.refresh_from_db()
    assert event.text_translations == {}


@pytest.mark.django_db
def test_이미_현재_해시로_저장된_이벤트에_다시_제출하면_already_current이고_덮어쓰지_않는다(make_event):
    event = _make_source_event(make_event)
    submitted_hash = source_hash(_event_fields(event))

    from events.translation_queue import submit_translation

    first_outcome = submit_translation(
        event_id=event.id, source_hash=submitted_hash, translations=_GOOD_TRANSLATIONS
    )
    assert first_outcome.status == "saved"

    different_translations = _deep_copy_translations(_GOOD_TRANSLATIONS)
    different_translations["en"]["work_title"] = "ONE PIECE"

    second_outcome = submit_translation(
        event_id=event.id, source_hash=submitted_hash, translations=different_translations
    )

    assert second_outcome.status == "already_current"
    assert second_outcome.saved == []

    event.refresh_from_db()
    assert event.text_translations["en"]["work_title"] == "One Piece"


@pytest.mark.django_db
def test_제출이_성공한_이벤트는_다음_대기_목록에서_빠진다(make_event):
    event = _make_source_event(make_event)
    submitted_hash = source_hash(_event_fields(event))

    from events.translation_queue import pending_events, submit_translation

    submit_translation(event_id=event.id, source_hash=submitted_hash, translations=_GOOD_TRANSLATIONS)

    assert [item["event_id"] for item in pending_events()] == []


@pytest.mark.django_db
def test_세_언어가_모두_격리된_제출_직후에도_대기_목록에서_빠진다(make_event):
    event = _make_source_event(make_event)
    translations = _deep_copy_translations(_GOOD_TRANSLATIONS)
    for language in translations:
        translations[language]["title"] = _SOURCE_FIELDS["title"]
    submitted_hash = source_hash(_event_fields(event))

    from events.translation_queue import pending_events, submit_translation

    submit_translation(event_id=event.id, source_hash=submitted_hash, translations=translations)

    assert [item["event_id"] for item in pending_events()] == []


@pytest.mark.django_db
def test_제출_한_번에_로그_한_줄이_남고_원문과_번역문은_들어가지_않는다(make_event, caplog):
    event = _make_source_event(make_event)
    submitted_hash = source_hash(_event_fields(event))

    from events.translation_queue import submit_translation

    with caplog.at_level(logging.INFO, logger="events.translation_queue"):
        submit_translation(
            event_id=event.id,
            source_hash=submitted_hash,
            translations=_GOOD_TRANSLATIONS,
            client_ip="203.0.113.5",
        )

    records = [r for r in caplog.records if r.name == "events.translation_queue"]
    assert len(records) == 1
    record = records[0]
    message = record.getMessage()

    assert record.levelname == "INFO"
    assert str(event.id) in message
    assert "saved" in message
    assert submitted_hash[:8] in message
    assert "203.0.113.5" in message
    assert _SOURCE_FIELDS["title"] not in message
    assert _GOOD_TRANSLATIONS["en"]["title"] not in message


@pytest.mark.django_db
@pytest.mark.parametrize(
    "setup_name",
    ["한글_잔존으로_ja가_격리된_제출", "manual_이벤트라서_거부된_제출"],
    ids=["한글_잔존으로_ja가_격리된_제출", "manual_이벤트라서_거부된_제출"],
)
def test_격리가_있는_제출과_거부된_제출은_WARNING_로그를_남긴다(make_event, caplog, setup_name):
    event = _make_source_event(make_event)

    from events.content_translation import SubmissionRejected
    from events.translation_queue import submit_translation

    if setup_name == "한글_잔존으로_ja가_격리된_제출":
        translations = _deep_copy_translations(_GOOD_TRANSLATIONS)
        translations["ja"]["title"] = "2026 도쿄 コミックマーケット"
        submitted_hash = source_hash(_event_fields(event))

        with caplog.at_level(logging.INFO, logger="events.translation_queue"):
            submit_translation(event_id=event.id, source_hash=submitted_hash, translations=translations)

        expected_fragment = "hangul_residue"
        expected_language = "ja"
    else:
        event.text_translations = {"manual": True, "source_hash": "임의-해시", "en": None, "ja": None, "zh-hans": None}
        event.save()
        submitted_hash = source_hash(_event_fields(event))

        with caplog.at_level(logging.INFO, logger="events.translation_queue"):
            with pytest.raises(SubmissionRejected):
                submit_translation(event_id=event.id, source_hash=submitted_hash, translations=_GOOD_TRANSLATIONS)

        expected_fragment = "manual_locked"
        expected_language = None

    records = [r for r in caplog.records if r.name == "events.translation_queue"]
    assert len(records) == 1
    record = records[0]
    message = record.getMessage()

    assert record.levelname == "WARNING"
    assert expected_fragment in message
    if expected_language is not None:
        assert expected_language in message
    assert _SOURCE_FIELDS["title"] not in message
    assert _GOOD_TRANSLATIONS["en"]["title"] not in message


@pytest.mark.django_db
def test_already_current_제출은_INFO_로그를_남긴다(make_event, caplog):
    event = _make_source_event(make_event)
    submitted_hash = source_hash(_event_fields(event))

    from events.translation_queue import submit_translation

    submit_translation(event_id=event.id, source_hash=submitted_hash, translations=_GOOD_TRANSLATIONS)

    with caplog.at_level(logging.INFO, logger="events.translation_queue"):
        caplog.clear()
        submit_translation(event_id=event.id, source_hash=submitted_hash, translations=_GOOD_TRANSLATIONS)

    records = [r for r in caplog.records if r.name == "events.translation_queue"]
    assert len(records) == 1
    assert records[0].levelname == "INFO"
    assert "already_current" in records[0].getMessage()


@pytest.mark.django_db
def test_제출은_행_잠금으로_이벤트를_읽는다(make_event):
    event = _make_source_event(make_event)
    submitted_hash = source_hash(_event_fields(event))

    from events.translation_queue import submit_translation

    with CaptureQueriesContext(connection) as ctx:
        submit_translation(event_id=event.id, source_hash=submitted_hash, translations=_GOOD_TRANSLATIONS)

    assert any("FOR UPDATE" in query["sql"].upper() for query in ctx.captured_queries)


@pytest.mark.django_db
def test_저장값이_dict가_아니어도_제출이_저장된다(make_event):
    event = _make_source_event(make_event)
    Event.objects.filter(pk=event.pk).update(text_translations=[])
    submitted_hash = source_hash(_event_fields(event))

    from events.translation_queue import submit_translation

    outcome = submit_translation(
        event_id=event.id, source_hash=submitted_hash, translations=_GOOD_TRANSLATIONS
    )

    assert outcome.status == "saved"
    event.refresh_from_db()
    assert event.text_translations == {
        "source_hash": submitted_hash,
        "manual": False,
        "en": _GOOD_TRANSLATIONS["en"],
        "ja": _GOOD_TRANSLATIONS["ja"],
        "zh-hans": _GOOD_TRANSLATIONS["zh-hans"],
    }
