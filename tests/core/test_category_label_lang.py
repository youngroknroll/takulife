"""카테고리 라벨 요소에 붙는 `lang` 속성 템플릿 태그를 검증한다
(트랙 59 확장 XS-16~XS-18). DB 없이 템플릿 렌더만 본다.
"""

from django.template import Context, Template
from django.utils import translation
import pytest

from core.vocab import CATEGORY_LABELS

pytestmark = pytest.mark.unit

_템플릿 = "{% load category_lang %}<span{% category_lang_attr label %}></span>"


@pytest.mark.parametrize(
    "언어",
    [
        pytest.param("en", id="영어"),
        pytest.param("ja", id="일본어"),
        pytest.param("zh-hans", id="중국어_간체"),
    ],
)
def test_비한국어_화면에서_한글_라벨로_속성을_그리면_ko_언어_속성이_붙는다(언어):
    with translation.override(언어):
        html = Template(_템플릿).render(Context({"label": "나이트 마켓"}))

    assert html == '<span lang="ko"></span>'


@pytest.mark.parametrize(
    "라벨",
    [
        pytest.param(CATEGORY_LABELS["popup_store"], id="번역된_고정_라벨"),
        pytest.param("Night Market", id="영문_DB_라벨"),
        pytest.param("", id="빈_라벨"),
    ],
)
def test_비한국어_화면에서_한글이_없는_라벨로_속성을_그리면_속성이_붙지_않는다(라벨):
    with translation.override("en"):
        html = Template(_템플릿).render(Context({"label": 라벨}))

    assert html == "<span></span>"


def test_한국어_화면에서는_한글_라벨이어도_ko_언어_속성이_붙지_않는다():
    with translation.override("ko"):
        html = Template(_템플릿).render(Context({"label": "나이트 마켓"}))

    assert html == "<span></span>"
