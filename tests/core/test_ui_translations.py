"""locale/*/LC_MESSAGES/*.mo가 있어야 한다 — `uv run django-admin
compilemessages --ignore .venv`(CI도 같은 스텝)."""

import json
import re
from html.parser import HTMLParser

import pytest
from django.test import Client

pytestmark = pytest.mark.web


# I18N-43 "찜"·"기록" msgctxt 분기 — 통계 칸(dt)과 동작(버튼/링크)은 영어로
# 품사가 갈려 한 msgid로 못 맞춘다. msgctxt "통계"/"동작"으로 가른다.
@pytest.mark.django_db
def test_영어_홈_스냅샷_통계_라벨은_Saved_Records이고_기록_대기_행_링크는_Add_record다(
    make_user, make_event
):
    from archive.models import UserEventStatus

    user = make_user()
    event = make_event(title="영어스냅샷테스트행사")
    UserEventStatus.objects.create(user=user, event=event, status=UserEventStatus.Status.VISITED)

    client = Client()
    client.force_login(user)
    resp = client.get("/", HTTP_ACCEPT_LANGUAGE="en")

    body = resp.content.decode()
    # 다른 문구(찜한 행사 "Saved events" 등)에 "Saved"/"Records"가 부분
    # 문자열로 섞여 나올 수 있어, 통계 <dt> 요소 단위로 좁혀 단언한다.
    assert re.search(
        r'<dt>\s*<span class="snapshot-stat-dot"[^>]*></span>\s*Saved\s*</dt>',
        body,
    ), "통계 칸(찜)에 'Saved'가 그대로 나오지 않았다"
    assert re.search(
        r'<dt>\s*<span class="snapshot-stat-dot"[^>]*></span>\s*Records\s*</dt>',
        body,
    ), "통계 칸(기록)에 'Records'가 그대로 나오지 않았다"
    assert not re.search(
        r'<dt>\s*<span class="snapshot-stat-dot"[^>]*></span>\s*Save\s*</dt>', body
    ), "통계 칸(찜)에 동작 번역 'Save'가 새어 들어왔다"
    assert re.search(r'<a class="record-action-link"[^>]*>\s*Add record\s*</a>', body), (
        "기록 대기 행 링크가 'Add record'로 나오지 않았다"
    )


class _LangTrackingParser(HTMLParser):
    """텍스트 노드가 찾는 문자열을 담고 있을 때, 그 시점의 가장 가까운
    조상(또는 자기 자신) `lang` 속성값을 기록한다 — 없으면 더 바깥쪽
    조상의 값을 물려받는다."""

    def __init__(self, needle):
        super().__init__()
        self.needle = needle
        self._lang_stack = []
        self.occurrence_langs = []

    def _push(self, tag, attrs):
        lang = dict(attrs).get("lang")
        self._lang_stack.append(
            lang if lang is not None else (self._lang_stack[-1] if self._lang_stack else None)
        )

    def handle_starttag(self, tag, attrs):
        self._push(tag, attrs)

    def handle_startendtag(self, tag, attrs):
        self._push(tag, attrs)
        self._lang_stack.pop()

    def handle_endtag(self, tag):
        if self._lang_stack:
            self._lang_stack.pop()

    def handle_data(self, data):
        if self.needle in data:
            self.occurrence_langs.append(self._lang_stack[-1] if self._lang_stack else None)


# I18N-12
@pytest.mark.django_db
@pytest.mark.parametrize(
    "code, expected",
    [
        pytest.param("en", "Privacy Policy", id="영어"),
        pytest.param("ja", "プライバシーポリシー", id="일본어"),
        pytest.param("zh-hans", "隐私政策", id="중국어_간체"),
    ],
)
def test_지원_언어별_홈_페이지에_번역된_문구가_보인다(code, expected):
    client = Client()

    response = client.get("/", HTTP_ACCEPT_LANGUAGE=code)

    assert expected in response.content.decode()


# I18N-12b
@pytest.mark.django_db
@pytest.mark.parametrize(
    "code, expected",
    [
        pytest.param("en", "Close", id="영어"),
        pytest.param("ja", "閉じる", id="일본어"),
        pytest.param("zh-hans", "关闭", id="중국어_간체"),
    ],
)
def test_지원_언어별_JS_카탈로그에_번역된_문구가_담긴다(code, expected):
    client = Client()

    response = client.get("/jsi18n/", HTTP_ACCEPT_LANGUAGE=code)

    # JavaScriptCatalog은 json.dumps(ensure_ascii=True)로 비ASCII를 \uXXXX로
    # 이스케이프하므로 같은 방식으로 직렬화해 비교한다.
    assert json.dumps(expected) in response.content.decode()


# I18N-22
@pytest.mark.django_db
@pytest.mark.parametrize(
    "code",
    [
        pytest.param("en", id="영어"),
        pytest.param("ja", id="일본어"),
        pytest.param("zh-hans", id="중국어_간체"),
    ],
)
def test_지원_언어별_홈에서_행사_제목은_한국어_원문_lang_ko로_표시된다(code, make_event):
    title = "트랙43테스트행사제목"
    make_event(title=title, location_name="트랙43테스트장소명")

    response = Client().get("/", HTTP_ACCEPT_LANGUAGE=code)

    parser = _LangTrackingParser(title)
    parser.feed(response.content.decode())

    assert parser.occurrence_langs, "행사 제목이 홈 응답에 나오지 않았다"
    assert all(lang == "ko" for lang in parser.occurrence_langs)
