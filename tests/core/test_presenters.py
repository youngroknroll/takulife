"""core.presenters — 홈 WebSite 구조화 데이터 조립 계약을 고정한다.

키 5개(@context, @type, name, alternateName, url) 전체를 고정해 추가 키가
조용히 섞여 들어가지 않게 한다.
"""
import pytest

pytestmark = pytest.mark.unit


def test_WebSite_구조화_데이터는_영문명과_한글_대체명과_사이트_URL만_담는다():
    from core.presenters import build_website_json_ld

    result = build_website_json_ld("http://testserver/")

    assert result == {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "takulife",
        "alternateName": "타쿠라이프",
        "url": "http://testserver/",
    }
