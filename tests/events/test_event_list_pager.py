"""Behavior under test: /events/ must render pagination through the shared
pager partial (templates/core/partials/_pager.html), the same component the
other seven paginated lists already use — not its own inline `<nav
class="pager">` markup with a `<span class="current">` current-page marker.

Contract asserted here is the shared partial's own contract (see its header
comment and core/templatetags/pager_tags.py), not any inline implementation
detail of core.views.event_list:
  - a page link carries class="pager-page"
  - the current page carries aria-current="page" (not a bare `.current` class)
  - page links preserve the active q/region/category/status filters and the
    active sort, the same way the other paginated lists already do.
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
    """Extract every pager page-link href (class="pager-page") from the
    rendered HTML body, ignoring order and any other links on the page."""
    import re

    return re.findall(r'<a class="pager-page[^"]*" href="([^"]+)"', body)


def _parse_pager_href_query(href):
    """Parse a pager href's querystring the way a browser does, not the way
    urllib alone would.

    The shared pager partial's `extra_query` starts with a literal '&'
    (core/partials/_pager.html), and Django's autoescape renders that as the
    HTML entity `&amp;` in the response body (core/views.py:836-837 already
    documents this: "템플릿이 href 안의 선행 & 를 &amp;로 이스케이프하고
    브라우저가 디코드한다"). `html.unescape` undoes that HTML-entity layer
    first; `urllib.parse.unquote` is a *different* layer (percent-encoding)
    and does not touch `&amp;` at all — skipping the entity-unescape leaves
    `&amp;sort=newest` intact, so parse_qs reads the key as "amp;sort"
    instead of "sort" and every assertion here would wrongly report the
    param as lost.
    """
    return parse_qs(urlparse(unquote(unescape(href))).query, keep_blank_values=True)
