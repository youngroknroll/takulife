"""트랙 43-3: 아카이브 서비스 함수의 검증 메시지 번역 계약.

서비스 함수는 직접 호출하면 그 시점의 활성 언어로 번역되므로
`translation.override`로 감싸 호출한다. 한국어는 현재 메시지를 글자 그대로,
영어·일본어·중국어는 한글이 없는 메시지를 받는다. HTTP 경계 테스트는
`test_archive_error_messages_i18n.py`에 있다(계층 분리 규약).
"""

import re
from datetime import date

import pytest
from django.core.exceptions import ValidationError
from django.utils import translation

from archive.services import (
    create_collection_item,
    create_personal_entry,
    update_collection_item,
)

pytestmark = [pytest.mark.django_db]

_KOREAN_RE = re.compile(r"[가-힣]")

_ALL_LANGS = ["ko", "en", "ja", "zh-hans"]


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


def _service_messages(lang, call):
    """서비스를 해당 언어로 호출해 ValidationError 메시지를 모은다."""
    with translation.override(lang):
        with pytest.raises(ValidationError) as caught:
            call()
        return _leaves(caught.value.message_dict)


# ---------------------------------------------------------------------------
# 서비스 메시지 7곳 (archive/services.py)
# ---------------------------------------------------------------------------


# Red 예측: en·ja·zh-hans는 한국어 메시지라 Red, ko는 Green 핀.
@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_장소가_아닌_종류로_개인_항목을_만들면_요청_언어의_메시지가_나온다(make_user, lang):
    user = make_user()

    messages = _service_messages(
        lang, lambda: create_personal_entry(user=user, kind="goods", title="굿즈")
    )

    _assert_message(lang, messages, "place 외의 kind로는 PersonalEntry를 생성할 수 없습니다.")


@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_수량이_음수인_굿즈를_만들면_요청_언어의_메시지가_나온다(make_user, lang):
    user = make_user()

    messages = _service_messages(
        lang,
        lambda: create_collection_item(user=user, name="굿즈", quantity=-1, tradeable_quantity=0),
    )

    _assert_message(lang, messages, "quantity는 0 이상이어야 합니다.")


@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_교환_가능_수량이_음수인_굿즈를_만들면_요청_언어의_메시지가_나온다(make_user, lang):
    user = make_user()

    messages = _service_messages(
        lang,
        lambda: create_collection_item(user=user, name="굿즈", quantity=1, tradeable_quantity=-1),
    )

    _assert_message(lang, messages, "tradeable_quantity는 0 이상이어야 합니다.")


@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_교환_가능_수량이_보유_수량을_넘는_굿즈를_만들면_요청_언어의_메시지가_나온다(
    make_user, lang
):
    user = make_user()

    messages = _service_messages(
        lang,
        lambda: create_collection_item(user=user, name="굿즈", quantity=1, tradeable_quantity=2),
    )

    _assert_message(lang, messages, "tradeable_quantity는 quantity 이하여야 합니다.")


@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_남의_방문_기록을_붙여_굿즈를_만들면_요청_언어의_메시지가_나온다(
    make_user, make_event, make_visit, lang
):
    user = make_user()
    other_visit = make_visit(make_user(), event=make_event(), visited_on=date(2026, 5, 1))

    messages = _service_messages(
        lang,
        lambda: create_collection_item(user=user, name="굿즈", visit_record=other_visit),
    )

    _assert_message(lang, messages, "visit_record는 요청한 사용자의 소유여야 합니다.")


@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_남의_방문_기록으로_굿즈를_수정하면_요청_언어의_메시지가_나온다(
    make_user, make_event, make_visit, make_collection_item, lang
):
    user = make_user()
    item = make_collection_item(user)
    other_visit = make_visit(make_user(), event=make_event(), visited_on=date(2026, 5, 1))

    messages = _service_messages(
        lang, lambda: update_collection_item(item=item, visit_record=other_visit)
    )

    _assert_message(lang, messages, "visit_record는 아이템 소유자의 소유여야 합니다.")


@pytest.mark.parametrize("lang", _ALL_LANGS)
def test_방문_기록과_다른_행사로_굿즈를_수정하면_요청_언어의_메시지가_나온다(
    make_user, make_event, make_visit, make_collection_item, lang
):
    user = make_user()
    visit = make_visit(user, event=make_event(title="행사 A"), visited_on=date(2026, 5, 1))
    item = make_collection_item(user, visit_record=visit, event=visit.event)
    other_event = make_event(title="행사 B")

    messages = _service_messages(lang, lambda: update_collection_item(item=item, event=other_event))

    _assert_message(
        lang,
        messages,
        "visit_record가 설정된 경우 event는 visit_record.event와 일치해야 합니다.",
    )
