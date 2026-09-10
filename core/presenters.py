"""사이트 수준 구조화 데이터(JSON-LD)를 조립한다.

이 모듈은 도메인 앱(events, archive 등)을 임포트하지 않는다(core -> 도메인
단방향 의존 유지).
"""
from .context_processors import BRAND_NAME_KO, PROJECT_NAME


def build_website_json_ld(site_url):
    """홈페이지 WebSite 구조화 데이터를 만든다.

    한글 표기는 context_processors 상수 한 곳에서만 가져온다. 이 블록은
    홈에서만 발행한다(다른 페이지에 넣으면 검색엔진이 대표 페이지를 고르기
    어려워진다).
    """
    return {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": PROJECT_NAME,
        "alternateName": BRAND_NAME_KO,
        "url": site_url,
    }
