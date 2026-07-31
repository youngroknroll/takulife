"""검증 대상 동작: /events/는 다른 7개 페이지네이션 목록과 같은 공용 페이저
파셜(templates/core/partials/_pager.html)로 페이지네이션을 렌더링해야
한다 — 자체 인라인 `<nav class="pager">` 마크업이나 `<span class="current">`
현재 페이지 표시가 아니다.

여기서 검증하는 계약은 공용 파셜 자체의 계약이다(그 헤더 주석과
core/templatetags/pager_tags.py 참고). core.views.event_list의 개별 구현이
아니다:
  - 페이지 링크는 class="pager-page"를 가진다
  - 현재 페이지는 aria-current="page"를 가진다(단순 `.current` 클래스가 아니다)
  - 페이지 링크는 다른 페이지네이션 목록과 마찬가지로 활성 q/region/category/status
    필터와 활성 정렬을 보존한다.
"""
from datetime import timedelta
from html import unescape
from urllib.parse import parse_qs, unquote, urlparse

import pytest
from django.test import Client
from django.utils import timezone

pytestmark = pytest.mark.web


@pytest.mark.django_db
class TestEventListSharedPagerMarkup:
    def test_두_페이지_이상의_행사_목록에서_공용_페이저_마크업이_사용된다(self, make_event):
        for i in range(15):
            make_event(title=f"공용페이저행사 {i}")

        resp = Client().get("/events/", {"page": 2})

        assert resp.status_code == 200
        body = resp.content.decode()
        assert 'class="pager-page' in body
        assert 'aria-current="page"' in body


@pytest.mark.django_db
class TestEventListPagerPreservesFilters:
    def test_필터와_검색어가_적용된_상태에서_페이저_페이지_링크에_필터가_보존된다(self, make_event):
        future_start = timezone.localdate() + timedelta(days=10)
        for i in range(15):
            make_event(
                title=f"필터보존행사 {i}",
                region="seoul",
                category="popup_store",
                start_date=future_start,
            )

        resp = Client().get(
            "/events/",
            {
                "q": "필터보존",
                "region": "seoul",
                "category": "popup_store",
                "status": "upcoming",
                "page": 2,
            },
        )

        assert resp.status_code == 200
        body = resp.content.decode()

        hrefs = [
            href
            for href in _pager_page_hrefs(body)
        ]
        assert hrefs, "페이저 페이지 링크가 렌더링되지 않음"
        for href in hrefs:
            params = _parse_pager_href_query(href)
            assert params.get("q") == ["필터보존"], f"{href}: 검색어 유실"
            assert params.get("region") == ["seoul"], f"{href}: 지역 필터 유실"
            assert params.get("category") == ["popup_store"], f"{href}: 카테고리 필터 유실"
            assert params.get("status") == ["upcoming"], f"{href}: 상태 필터 유실"


@pytest.mark.django_db
class TestEventListPagerPreservesSort:
    def test_정렬이_적용된_상태에서_페이저_페이지_링크에_정렬이_보존된다(self, make_event):
        for i in range(15):
            make_event(title=f"정렬보존행사 {i}")

        resp = Client().get("/events/", {"sort": "newest", "page": 2})

        assert resp.status_code == 200
        body = resp.content.decode()

        hrefs = _pager_page_hrefs(body)
        assert hrefs, "페이저 페이지 링크가 렌더링되지 않음"
        for href in hrefs:
            params = _parse_pager_href_query(href)
            assert params.get("sort") == ["newest"], f"{href}: 정렬 유실"


def _pager_page_hrefs(body):
    """렌더링된 HTML 본문에서 페이저 페이지 링크(class="pager-page")의 href를
    순서·다른 링크와 무관하게 모두 추출한다."""
    import re

    return re.findall(r'<a class="pager-page[^"]*" href="([^"]+)"', body)


def _parse_pager_href_query(href):
    """페이저 href의 쿼리스트링을 urllib 단독이 아니라 브라우저처럼 파싱한다.

    공용 페이저 파셜의 `extra_query`는 리터럴 '&'로 시작하는데
    (core/partials/_pager.html), Django의 자동 이스케이프가 응답 본문에서
    이를 HTML 엔티티 `&amp;`로 렌더링한다(core/views.py:836-837에 이미
    문서화됨: "템플릿이 href 안의 선행 & 를 &amp;로 이스케이프하고 브라우저가
    디코드한다"). `html.unescape`가 먼저 그 HTML 엔티티 계층을 되돌리고,
    `urllib.parse.unquote`는 전혀 다른 계층(퍼센트 인코딩)이라 `&amp;`를
    건드리지 않는다 — 엔티티 언이스케이프를 생략하면 `&amp;sort=newest`가
    그대로 남아 parse_qs가 키를 "sort"가 아닌 "amp;sort"로 읽어 모든 단언이
    잘못 유실로 보고한다.
    """
    return parse_qs(urlparse(unquote(unescape(href))).query, keep_blank_values=True)
