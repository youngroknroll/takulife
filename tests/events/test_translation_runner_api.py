"""번역 러너 API 인증·계약 테스트 — X-Runner-Token 헤더와 응답/상태 코드 계약.

api/translation/runner/pending/·submit/ 경로가 아직 config/urls.py에 없다
(트랙 44-1 묶음 ⑤ 구현 전) → 전부 경로 부재 404로 Red가 될 것으로 예상한다.
"""
import logging

import pytest

from core.runner_auth import RunnerTokenThrottle
from events.content_translation import TRANSLATED_FIELDS, source_hash

pytestmark = [pytest.mark.django_db, pytest.mark.web]

PENDING_URL = "/api/translation/runner/pending/"
SUBMIT_URL = "/api/translation/runner/submit/"
HEARTBEAT_URL = "/api/discovery/runner/heartbeat/"

_RUNNER_TOKEN = "runner-secret"

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


@pytest.fixture
def runner_headers(settings):
    """유효 러너 토큰을 설정하고 헤더 kwargs를 돌려준다(tests/drafts/test_discovery_runner_api.py와 같은 관례)."""
    settings.DRAFT_DISCOVERY_RUNNER_TOKEN = _RUNNER_TOKEN
    return {"HTTP_X_RUNNER_TOKEN": _RUNNER_TOKEN}


def _make_source_event(make_event, **overrides):
    return make_event(**{**_SOURCE_FIELDS, **overrides})


def _event_fields(event):
    return {name: getattr(event, name) for name in TRANSLATED_FIELDS}


def _deep_copy_translations(translations):
    return {language: dict(fields) for language, fields in translations.items()}


@pytest.mark.parametrize("url", [PENDING_URL, SUBMIT_URL], ids=["pending", "submit"])
@pytest.mark.parametrize(
    "token_setting, header_kwargs",
    [
        (_RUNNER_TOKEN, {}),
        (_RUNNER_TOKEN, {"HTTP_X_RUNNER_TOKEN": "wrong-token"}),
        ("", {"HTTP_X_RUNNER_TOKEN": _RUNNER_TOKEN}),
    ],
    ids=["헤더_없음", "틀린_헤더", "설정_토큰이_빈_문자열"],
)
def test_토큰이_없거나_틀리거나_설정이_비면_번역_러너_엔드포인트가_403이다(
    client, settings, url, token_setting, header_kwargs
):
    settings.DRAFT_DISCOVERY_RUNNER_TOKEN = token_setting

    response = client.post(url, data={}, content_type="application/json", **header_kwargs)

    assert response.status_code == 403


def test_대기가_없으면_200과_빈_목록이다(client, runner_headers):
    response = client.post(PENDING_URL, data={}, content_type="application/json", **runner_headers)

    assert response.status_code == 200
    assert response.json() == {"events": []}


def test_대기_이벤트가_있으면_id_해시_원문_필드를_돌려준다(client, runner_headers, make_event):
    event = _make_source_event(make_event)
    fields = _event_fields(event)
    expected_hash = source_hash(fields)

    response = client.post(PENDING_URL, data={}, content_type="application/json", **runner_headers)

    assert response.status_code == 200
    assert response.json() == {
        "events": [
            {"event_id": event.id, "source_hash": expected_hash, "fields": fields}
        ]
    }


@pytest.mark.parametrize("url", [PENDING_URL, SUBMIT_URL], ids=["pending", "submit"])
def test_메서드는_POST만_허용한다(client, runner_headers, url):
    response = client.get(url, **runner_headers)

    assert response.status_code == 405


def test_정상_제출은_200으로_세_언어를_저장한다(client, runner_headers, make_event):
    event = _make_source_event(make_event)
    submitted_hash = source_hash(_event_fields(event))

    response = client.post(
        SUBMIT_URL,
        data={"event_id": event.id, "source_hash": submitted_hash, "translations": _GOOD_TRANSLATIONS},
        content_type="application/json",
        **runner_headers,
    )

    assert response.status_code == 200
    assert response.json() == {"status": "saved", "saved": ["en", "ja", "zh-hans"], "quarantined": {}}

    event.refresh_from_db()
    assert event.text_translations == {
        "source_hash": submitted_hash,
        "manual": False,
        "en": _GOOD_TRANSLATIONS["en"],
        "ja": _GOOD_TRANSLATIONS["ja"],
        "zh-hans": _GOOD_TRANSLATIONS["zh-hans"],
    }


def test_한국어가_남은_언어만_격리하고_나머지는_저장한다(client, runner_headers, make_event):
    event = _make_source_event(make_event)
    translations = _deep_copy_translations(_GOOD_TRANSLATIONS)
    translations["ja"]["title"] = "2026 도쿄 コミックマーケット"
    submitted_hash = source_hash(_event_fields(event))

    response = client.post(
        SUBMIT_URL,
        data={"event_id": event.id, "source_hash": submitted_hash, "translations": translations},
        content_type="application/json",
        **runner_headers,
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "saved",
        "saved": ["en", "zh-hans"],
        "quarantined": {"ja": "hangul_residue"},
    }

    event.refresh_from_db()
    assert event.text_translations["ja"] is None


def test_해시가_낡았으면_409이고_저장하지_않는다(client, runner_headers, make_event):
    event = _make_source_event(make_event)
    stale_hash = source_hash(_event_fields(event))
    event.title = "원문이 바뀐 뒤"
    event.save()

    response = client.post(
        SUBMIT_URL,
        data={"event_id": event.id, "source_hash": stale_hash, "translations": _GOOD_TRANSLATIONS},
        content_type="application/json",
        **runner_headers,
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "stale_source"}

    event.refresh_from_db()
    assert event.text_translations == {}


def test_전체_거부와_언어_격리는_상태_코드로_구분된다(client, runner_headers, make_event):
    quarantine_event = _make_source_event(make_event)
    quarantine_translations = _deep_copy_translations(_GOOD_TRANSLATIONS)
    quarantine_translations["ja"]["title"] = "2026 도쿄 コミックマーケット"
    quarantine_hash = source_hash(_event_fields(quarantine_event))

    quarantine_response = client.post(
        SUBMIT_URL,
        data={
            "event_id": quarantine_event.id,
            "source_hash": quarantine_hash,
            "translations": quarantine_translations,
        },
        content_type="application/json",
        **runner_headers,
    )

    assert quarantine_response.status_code == 200
    assert "status" in quarantine_response.json()
    assert "detail" not in quarantine_response.json()

    rejected_event = _make_source_event(make_event)
    stale_hash = source_hash(_event_fields(rejected_event))
    rejected_event.title = "원문이 또 바뀐 뒤"
    rejected_event.save()

    rejected_response = client.post(
        SUBMIT_URL,
        data={"event_id": rejected_event.id, "source_hash": stale_hash, "translations": _GOOD_TRANSLATIONS},
        content_type="application/json",
        **runner_headers,
    )

    assert rejected_response.status_code == 409
    assert "detail" in rejected_response.json()
    assert "status" not in rejected_response.json()


def test_없거나_게시되지_않은_이벤트는_404이다_없는_이벤트(client, runner_headers):
    payload = {"event_id": 999999, "source_hash": "아무해시", "translations": _GOOD_TRANSLATIONS}

    response = client.post(SUBMIT_URL, data=payload, content_type="application/json", **runner_headers)

    assert response.status_code == 404
    assert response.json() == {"detail": "not_found"}


def test_없거나_게시되지_않은_이벤트는_404이다_초안_이벤트(client, runner_headers, make_draft_event):
    event = make_draft_event(**_SOURCE_FIELDS)
    submitted_hash = source_hash(_event_fields(event))

    response = client.post(
        SUBMIT_URL,
        data={"event_id": event.id, "source_hash": submitted_hash, "translations": _GOOD_TRANSLATIONS},
        content_type="application/json",
        **runner_headers,
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "not_found"}


def test_수동_확정된_이벤트는_409이고_덮어쓰지_않는다(client, runner_headers, make_event):
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

    response = client.post(
        SUBMIT_URL,
        data={"event_id": event.id, "source_hash": submitted_hash, "translations": _GOOD_TRANSLATIONS},
        content_type="application/json",
        **runner_headers,
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "manual_locked"}

    event.refresh_from_db()
    assert event.text_translations == locked_state


def test_이미_현재_해시로_저장됐으면_already_current를_돌려준다(client, runner_headers, make_event):
    event = _make_source_event(make_event)
    submitted_hash = source_hash(_event_fields(event))
    payload = {"event_id": event.id, "source_hash": submitted_hash, "translations": _GOOD_TRANSLATIONS}

    first_response = client.post(SUBMIT_URL, data=payload, content_type="application/json", **runner_headers)
    assert first_response.status_code == 200

    second_response = client.post(SUBMIT_URL, data=payload, content_type="application/json", **runner_headers)

    assert second_response.status_code == 200
    assert second_response.json() == {"status": "already_current", "saved": [], "quarantined": {}}


@pytest.mark.parametrize(
    "scenario",
    ["ja_키_누락", "NUL_문자_포함", "translations_키_없음"],
    ids=["ja_키_누락", "NUL_문자_포함", "translations_키_없음"],
)
def test_구조가_틀린_번역은_400_schema이고_NUL은_400_nul이다(client, runner_headers, make_event, scenario):
    event = _make_source_event(make_event)
    submitted_hash = source_hash(_event_fields(event))

    if scenario == "ja_키_누락":
        broken_translations = _deep_copy_translations(_GOOD_TRANSLATIONS)
        del broken_translations["ja"]
        payload = {"event_id": event.id, "source_hash": submitted_hash, "translations": broken_translations}
        expected_detail = "schema"
    elif scenario == "NUL_문자_포함":
        broken_translations = _deep_copy_translations(_GOOD_TRANSLATIONS)
        broken_translations["en"]["title"] = broken_translations["en"]["title"] + chr(0)
        payload = {"event_id": event.id, "source_hash": submitted_hash, "translations": broken_translations}
        expected_detail = "nul"
    else:
        payload = {"event_id": event.id, "source_hash": submitted_hash}
        expected_detail = "schema"

    response = client.post(SUBMIT_URL, data=payload, content_type="application/json", **runner_headers)

    assert response.status_code == 400
    assert response.json() == {"detail": expected_detail}

    event.refresh_from_db()
    assert event.text_translations == {}


@pytest.mark.parametrize(
    "payload",
    [
        [1, 2, 3],
        {"event_id": "1", "source_hash": "아무해시", "translations": _GOOD_TRANSLATIONS},
        {"event_id": True, "source_hash": "아무해시", "translations": _GOOD_TRANSLATIONS},
        {"event_id": 1, "source_hash": 123, "translations": _GOOD_TRANSLATIONS},
    ],
    ids=["JSON_배열", "event_id가_문자열", "event_id가_Bool", "source_hash가_정수"],
)
def test_본문_모양이_틀리면_400_invalid_payload이다(client, runner_headers, payload):
    response = client.post(SUBMIT_URL, data=payload, content_type="application/json", **runner_headers)

    assert response.status_code == 400
    assert response.json() == {"detail": "invalid_payload"}


def test_제출_로그에_요청_IP가_남는다(client, runner_headers, make_event, caplog):
    event = _make_source_event(make_event)
    submitted_hash = source_hash(_event_fields(event))

    with caplog.at_level(logging.INFO, logger="events.translation_queue"):
        response = client.post(
            SUBMIT_URL,
            data={"event_id": event.id, "source_hash": submitted_hash, "translations": _GOOD_TRANSLATIONS},
            content_type="application/json",
            REMOTE_ADDR="203.0.113.7",
            **runner_headers,
        )

    assert response.status_code == 200
    records = [r for r in caplog.records if r.name == "events.translation_queue"]
    assert len(records) == 1
    assert "203.0.113.7" in records[0].getMessage()


def test_번역_러너와_드래프트_러너는_서로의_스로틀_예산을_쓰지_않는다(client, runner_headers, monkeypatch, clear_cache):
    # THROTTLE_RATES는 임포트 시점에 고정되는 클래스 속성이라 설정만 바꿔서는
    # 반영되지 않는다 — 클래스 속성 자체를 직접 덮어쓴다(기존 드래프트 러너
    # 테스트와 같은 방식).
    monkeypatch.setattr(
        RunnerTokenThrottle,
        "THROTTLE_RATES",
        {"discovery_runner": "2/minute", "translation_runner": "2/minute"},
    )

    client.post(HEARTBEAT_URL, data={}, content_type="application/json", **runner_headers)
    client.post(HEARTBEAT_URL, data={}, content_type="application/json", **runner_headers)
    third_heartbeat = client.post(HEARTBEAT_URL, data={}, content_type="application/json", **runner_headers)

    assert third_heartbeat.status_code == 429

    pending_response = client.post(PENDING_URL, data={}, content_type="application/json", **runner_headers)

    assert pending_response.status_code == 200


def test_번역_러너는_자기_scope_한도를_넘으면_429이다(client, runner_headers, monkeypatch, clear_cache):
    monkeypatch.setattr(
        RunnerTokenThrottle,
        "THROTTLE_RATES",
        {"discovery_runner": "2/minute", "translation_runner": "2/minute"},
    )

    first_response = client.post(PENDING_URL, data={}, content_type="application/json", **runner_headers)
    second_response = client.post(PENDING_URL, data={}, content_type="application/json", **runner_headers)
    third_response = client.post(PENDING_URL, data={}, content_type="application/json", **runner_headers)

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert third_response.status_code == 429


def test_번역_러너_스로틀_scope가_분당_60회로_등록되어_있다(settings):
    rate = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["translation_runner"]

    assert rate == "60/minute"
