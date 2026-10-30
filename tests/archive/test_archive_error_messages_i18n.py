"""트랙 43-3: 아카이브 서비스·시리얼라이저·뷰의 검증 메시지 번역 계약.

한국어 요청은 현재 메시지를 글자 그대로 받고, 영어·일본어·중국어 요청은
한글이 없는 메시지를 받는다(영문 식별자 `quantity` 등은 남아도 된다).
서비스 함수 직접 호출 테스트는
`test_archive_service_messages_i18n_services.py`에 있다. 영어 `detail` 세 곳은 번역 대상이
아니다 — `code`가 언어와 무관하게 같고 `detail`은 영어 그대로임을 고정한다.
"""

from datetime import date
import re

import pytest

pytestmark = [pytest.mark.django_db]

_KOREAN_RE = re.compile(r"[가-힣]")

_ALL_LANGS = ["ko", "en", "ja", "zh-hans"]

_ACCEPT_LANGUAGE = {
    "ko": {},
    "en": {"HTTP_ACCEPT_LANGUAGE": "en"},
    "ja": {"HTTP_ACCEPT_LANGUAGE": "ja"},
    "zh-hans": {"HTTP_ACCEPT_LANGUAGE": "zh-hans"},
}

_EXACTLY_ONE_TARGET = "event 또는 personal_entry 중 정확히 하나를 지정해야 합니다."
_TARGET_NOT_ALLOWED = "이 personal_entry는 이 작업의 대상이 될 수 없습니다."


def _leaves(value):
    """중첩된 dict·list 안의 문자열 값을 전부 평평하게 모은다."""
    if isinstance(value, dict):
        return [leaf for item in value.values() for leaf in _leaves(item)]
    if isinstance(value, (list, tuple)):
        return [leaf for item in value for leaf in _leaves(item)]
    return [str(value)]


def _assert_message(lang, messages, korean_message):
    """한국어는 현재 문구 그대로, 그 밖의 언어는 한글이 없어야 한다."""
    assert messages, "검증 메시지가 하나도 나오지 않았다"
    if lang == "ko":
        assert korean_message in messages
    else:
        assert [m for m in messages if _KOREAN_RE.search(m)] == []


def _post(client, lang, path, payload):
    return client.post(path, payload, content_type="application/json", **_ACCEPT_LANGUAGE[lang])


def _patch(client, lang, path, payload):
    return client.patch(path, payload, content_type="application/json", **_ACCEPT_LANGUAGE[lang])


# ---------------------------------------------------------------------------
# 시리얼라이저 메시지 5곳 (archive/serializers.py)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_대상_없이_찜을_등록하면_요청_언어의_메시지가_나온다(client, make_user, lang):
    client.force_login(make_user())

    response = _post(client, lang, "/api/event-interests/", {})

    assert response.status_code == 400
    _assert_message(lang, _leaves(response.json()), _EXACTLY_ONE_TARGET)


@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_굿즈_종류_개인_항목을_찜하면_요청_언어의_메시지가_나온다(
    client, make_user, make_entry, lang
):
    user = make_user()
    client.force_login(user)
    entry = make_entry(user, kind="goods")

    response = _post(client, lang, "/api/event-interests/", {"personal_entry": entry.id})

    assert response.status_code == 400
    _assert_message(lang, _leaves(response.json()), _TARGET_NOT_ALLOWED)


@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_대상_없이_행사_상태를_등록하면_요청_언어의_메시지가_나온다(client, make_user, lang):
    client.force_login(make_user())

    response = _post(client, lang, "/api/user-event-statuses/", {"status": "planned"})

    assert response.status_code == 400
    _assert_message(lang, _leaves(response.json()), _EXACTLY_ONE_TARGET)


@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_상태_없이_행사_상태를_수정하면_요청_언어의_메시지가_나온다(
    client, make_user, make_event, make_status, lang
):
    user = make_user()
    client.force_login(user)
    status_row = make_status(user, event=make_event())

    response = _patch(client, lang, f"/api/user-event-statuses/{status_row.id}/", {})

    assert response.status_code == 400
    _assert_message(lang, _leaves(response.json()), "상태를 지정해야 합니다.")


@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_대상_없이_방문_기록을_등록하면_요청_언어의_메시지가_나온다(client, make_user, lang):
    client.force_login(make_user())

    response = _post(client, lang, "/api/visit-records/", {"visited_on": "2026-05-26"})

    assert response.status_code == 400
    _assert_message(lang, _leaves(response.json()), _EXACTLY_ONE_TARGET)


@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_굿즈_종류_개인_항목으로_방문_기록을_등록하면_요청_언어의_메시지가_나온다(
    client, make_user, make_entry, lang
):
    user = make_user()
    client.force_login(user)
    entry = make_entry(user, kind="goods")

    response = _post(
        client,
        lang,
        "/api/visit-records/",
        {"personal_entry": entry.id, "visited_on": "2026-05-26"},
    )

    assert response.status_code == 400
    _assert_message(lang, _leaves(response.json()), _TARGET_NOT_ALLOWED)


# ---------------------------------------------------------------------------
# 뷰 메시지 2곳 (archive/views.py)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_방문_기록이_있는_행사를_예정으로_등록하면_요청_언어의_메시지가_나온다(
    client, make_user, make_event, make_visit, lang
):
    user = make_user()
    client.force_login(user)
    event = make_event()
    make_visit(user, event=event, visited_on=date(2026, 5, 1))

    response = _post(
        client,
        lang,
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
    )

    assert response.status_code == 400
    _assert_message(
        lang,
        _leaves(response.json()),
        "이미 방문 기록이 있는 항목은 이 상태로 등록할 수 없습니다.",
    )


@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_방문_기록이_있는_행사_상태를_예정으로_되돌리면_요청_언어의_메시지가_나온다(
    client, make_user, make_event, make_status, make_visit, lang
):
    user = make_user()
    client.force_login(user)
    event = make_event()
    status_row = make_status(user, event=event, status="visited")
    make_visit(user, event=event, visited_on=date(2026, 5, 1))

    response = _patch(
        client, lang, f"/api/user-event-statuses/{status_row.id}/", {"status": "planned"}
    )

    assert response.status_code == 400
    _assert_message(
        lang,
        _leaves(response.json()),
        "이미 방문 기록이 있는 항목은 이 상태로 되돌릴 수 없습니다.",
    )


# ---------------------------------------------------------------------------
# 영어 detail 세 곳은 번역하지 않는다 — Green 핀(변이로 Red 증명 필요)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_이미_찜한_행사의_409는_언어와_무관하게_같은_code와_영어_detail을_준다(
    client, make_user, make_event, make_interest, lang
):
    user = make_user()
    client.force_login(user)
    event = make_event()
    make_interest(user, event=event)

    response = _post(client, lang, "/api/event-interests/", {"event": event.id})

    assert response.status_code == 409
    assert response.json() == {
        "code": "duplicate_event_interest",
        "detail": "Event interest already exists for this event.",
    }


@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_이미_있는_행사_상태의_409는_언어와_무관하게_같은_code와_영어_detail을_준다(
    client, make_user, make_event, make_status, lang
):
    user = make_user()
    client.force_login(user)
    event = make_event()
    make_status(user, event=event)

    response = _post(
        client,
        lang,
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "code": "duplicate_user_event_status",
        "detail": "User event status already exists for this event.",
    }


@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_방문_완료_처리_중_중복_상태_409는_언어와_무관하게_같은_code와_영어_detail을_준다(
    client, make_user, make_event, monkeypatch, lang
):
    from archive import views as archive_views

    def raising_complete_visit_with_record(**kwargs):
        raise archive_views.DuplicateUserEventStatusError()

    monkeypatch.setattr(
        archive_views, "complete_visit_with_record", raising_complete_visit_with_record
    )
    client.force_login(make_user())
    event = make_event()

    response = _post(
        client,
        lang,
        "/api/visit-records/",
        {"event": event.id, "visited_on": "2026-05-26"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "code": "duplicate_user_event_status",
        "detail": "User event status already exists for this event.",
    }
