"""트랙 43-1 UI 다국어 기반 — jsi18n 경로, Accept-Language에 따른 html lang,
/i18n/setlang/ POST로 언어 전환."""
import re

import pytest
from django.conf import settings
from django.test import Client

pytestmark = pytest.mark.web


def _extract_html_lang(content):
    """<html lang="..."> 속성값만 뽑아내는 파싱 잡음 전용 보조 함수."""
    match = re.search(r'<html[^>]*\blang="([^"]*)"', content)
    return match.group(1) if match else None


# I18N-7
@pytest.mark.django_db
def test_jsi18n_경로는_200과_gettext_정의를_포함한다():
    client = Client()

    response = client.get("/jsi18n/")

    assert response.status_code == 200
    assert b"django.gettext =" in response.content


# I18N-9
@pytest.mark.django_db
def test_Accept_Language_헤더에_따라_홈_html_lang_속성이_결정된다():
    client = Client()

    response_default = client.get("/")
    response_en = client.get("/", HTTP_ACCEPT_LANGUAGE="en")

    lang_default = _extract_html_lang(response_default.content.decode())
    lang_en = _extract_html_lang(response_en.content.decode())

    assert lang_default != lang_en
    assert lang_en == "en"


# I18N-10
@pytest.mark.django_db
def test_setlang_POST로_언어를_바꾸면_이후_요청의_html_lang이_바뀐다():
    client = Client()

    response_setlang = client.post("/i18n/setlang/", {"language": "ja", "next": "/"})
    response_home = client.get("/")

    assert response_setlang.status_code == 302
    assert response_setlang["Location"] == "/"
    morsel = response_setlang.cookies["django_language"]
    assert morsel.value == "ja"
    assert morsel["httponly"] is True
    assert bool(morsel["secure"]) == settings.LANGUAGE_COOKIE_SECURE
    assert morsel["samesite"] == "Lax"
    assert '<html lang="ja">' in response_home.content.decode()


# I18N-11
@pytest.mark.django_db
@pytest.mark.parametrize(
    "code",
    [
        pytest.param("fr", id="Django에_번역_파일이_있는_다른_언어"),
        pytest.param("xx", id="번역_파일도_없는_코드"),
    ],
)
def test_지원_목록에_없는_언어로_setlang_POST해도_이후_요청의_html_lang은_ko로_유지된다(code):
    """fr은 Django 기본 로케일이 있어 setlang이 쿠키를 설정하지만, LANGUAGES에
    없으므로 LocaleMiddleware가 읽을 때 무시해 html lang은 그대로 ko다."""
    client = Client()

    client.post("/i18n/setlang/", {"language": code, "next": "/"})
    response_home = client.get("/")

    assert '<html lang="ko">' in response_home.content.decode()


# I18N-19
@pytest.mark.django_db
@pytest.mark.parametrize(
    "unsafe_next",
    [
        pytest.param("https://evil.example/", id="외부_호스트"),
        pytest.param("javascript:alert(1)", id="javascript_스킴"),
        pytest.param("//evil.example/", id="스킴_없는_프로토콜_상대_URL"),
    ],
)
def test_setlang_POST의_next가_외부_주소면_같은_사이트의_루트로_리다이렉트된다(unsafe_next):
    """Referer 헤더가 없는 요청에서 `next`가 허용 호스트 바깥이면
    Django의 `set_language`가 자체적으로 `/`로 떨어뜨린다."""
    client = Client()

    response = client.post("/i18n/setlang/", {"language": "ja", "next": unsafe_next})

    assert response.status_code == 302
    assert response["Location"] == "/"
