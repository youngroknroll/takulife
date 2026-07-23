"""Tests for the public browse page view (core.views.event_list).

Behavior under test: an invalid or unmatched filter value renders the empty
state ("행사 없음"), never a hard error screen. The JSON API keeps rejecting the
same input with 400 (covered in test_events_api.py) — only the browse page
degrades gracefully.
"""
import re
from html import unescape
from urllib.parse import parse_qs, quote, urlparse

import pytest
from django.test import Client

from core.vocab import EVENT_SORT, EVENT_SORT_LABELS

pytestmark = pytest.mark.web


@pytest.mark.django_db
class TestEventListInvalidFilters:
    def test_존재하지_않는_상태_값으로_필터링하면_오류_없이_빈_상태_문구를_보여준다(self, make_event):
        make_event(title="Live event")

        resp = Client().get("/events/", {"status": "zzz"})

        assert resp.status_code == 200
        body = resp.content.decode()
        assert "조건에 맞는 이벤트가 없어요" in body
        assert "잘못된 필터 값" not in body

    def test_존재하지_않는_카테고리_값으로_필터링하면_빈_상태_문구를_보여준다(self, make_event):
        make_event(title="Live event")

        resp = Client().get("/events/", {"category": "zzz"})

        assert resp.status_code == 200
        assert "조건에 맞는 이벤트가 없어요" in resp.content.decode()

    def test_유효한_카테고리로_필터링하면_일치하는_행사만_노출된다(self, make_event):
        make_event(title="Popup match", category="popup_store")

        resp = Client().get("/events/", {"category": "popup_store"})

        assert resp.status_code == 200
        body = resp.content.decode()
        assert "검색 결과" in body
        assert "Popup match" in body

    def test_지역_값을_여러_개_전달하면_OR_조건으로_일치하는_행사를_모두_보여준다(self, make_event):
        seoul = make_event(title="Seoul one", region="seoul")
        gyeonggi = make_event(title="Gyeonggi one", region="gyeonggi")
        make_event(title="Busan one", region="busan")

        resp = Client().get("/events/?region=seoul&region=gyeonggi")

        assert resp.status_code == 200
        body = resp.content.decode()
        assert "Seoul one" in body
        assert "Gyeonggi one" in body
        assert "Busan one" not in body

    def test_사이드바_폼의_빈_상태_값은_필터_없음으로_처리되어_다른_필터와_함께_정상_동작한다(self, make_event):
        """The sidebar form always submits status="" (전체) and sort="";
        a blank status must mean "no status filter", not an error."""
        make_event(title="Seoul match", region="seoul")

        resp = Client().get(
            "/events/", {"region": "seoul", "status": "", "sort": ""}
        )

        assert resp.status_code == 200
        body = resp.content.decode()
        assert "검색 결과" in body
        assert "Seoul match" in body


@pytest.mark.django_db
class TestEventListAuthenticatedRows:
    """A logged-in viewer's own status/interest is attached to browse cards
    (core.views._attach_display authenticated branch)."""

    def test_로그인_사용자가_행사_목록을_보면_카드에_본인_상태와_찜_여부가_반영된다(
        self, make_event, make_user
    ):
        from archive.models import EventInterest, UserEventStatus

        event = make_event(title="내 행사")
        user = make_user()
        UserEventStatus.objects.create(user=user, event=event, status="planned")
        EventInterest.objects.create(user=user, event=event)

        client = Client()
        client.force_login(user)
        resp = client.get("/events/")

        assert resp.status_code == 200
        row = next(r for r in resp.context["event_rows"] if r["event"].id == event.id)
        assert row["user_status"] == "planned"
        assert row["user_interested"] is True


@pytest.mark.django_db
class TestEventListRegionLabel:
    """Each row carries a Korean region_label for the card's place line
    (§6.2: 지역 라벨 + location_name 합성 표기)."""

    def test_지역이_설정된_행사는_목록_카드에_한글_지역_라벨을_담는다(self, make_event):
        make_event(title="서울 행사", region="seoul")

        resp = Client().get("/events/")

        row = next(r for r in resp.context["event_rows"] if r["event"].title == "서울 행사")
        assert row["region_label"] == "서울"

    def test_지역이_없는_행사는_목록_카드의_지역_라벨이_빈_값이다(self, make_event):
        make_event(title="지역 없음", region="")

        resp = Client().get("/events/")

        row = next(r for r in resp.context["event_rows"] if r["event"].title == "지역 없음")
        assert row["region_label"] == ""


@pytest.mark.django_db
class TestEventListActiveFilterChips:
    def test_검색어로_필터링하면_활성_필터_칩에_검색어가_표시된다(self, make_event):
        make_event(title="공연 행사")

        resp = Client().get("/events/", {"q": "공연"})

        assert resp.status_code == 200
        assert "검색: 공연" in resp.context["active_filter_chips"]


@pytest.mark.django_db
class TestEventListPagerQEncoding:
    """The pager's ?q= link must URL-encode the search term, so a value
    containing '#' isn't truncated into a URL fragment on click, losing the
    rest of the query string.

    /events/ now renders pagination through the shared pager partial
    (templates/core/partials/_pager.html), whose extra_query is built with
    urllib.parse.urlencode (quote_plus-style) — the same encoding the other
    seven paginated lists already use (core/views.py:857). The old inline
    pager this replaced used Django's `|urlencode` template filter
    (urllib.parse.quote-style), which escaped '+'/space as %2B/%20 instead of
    +. Both styles round-trip to the identical original string with no data
    loss, so the '+'/space case below asserts the round-trip outcome (decoded
    q equals the original search term) rather than pinning one literal
    encoding — only the '#' case, whose whole point is avoiding a URL
    fragment, still asserts the specific escaped literal."""

    def test_검색어에_해시_기호가_있으면_페이저_링크의_q_값이_URL_인코딩되어_잘리지_않는다(self, make_event):
        for i in range(11):
            make_event(title=f"#콜라보 행사 {i}")

        resp = Client().get("/events/", {"q": "#콜라보"})

        assert resp.status_code == 200
        body = resp.content.decode()
        assert f"q={quote('#콜라보')}" in body
        assert "&q=#" not in body

    def test_검색어에_더하기와_공백이_있으면_페이저_링크의_q_값이_원래_검색어로_보존된다(self, make_event):
        """'+'/space must never reach the href unescaped (raw form-encoding
        chars in a query value are ambiguous), and the pager link must decode
        back to the exact original search term 'a+b c' — regardless of
        whether the encoder chose %2B/%20 or %2B/+ to represent it."""
        for i in range(11):
            make_event(title=f"a+b c 행사 {i}")

        resp = Client().get("/events/", {"q": "a+b c"})

        assert resp.status_code == 200
        body = resp.content.decode()
        assert "q=a+b c" not in body

        href = next(
            href
            for href in re.findall(r'href="([^"]*[?&]page=[^"]*)"', body)
            if "q=" in href
        )
        query = parse_qs(urlparse(unescape(href)).query, keep_blank_values=True)
        assert query.get("q") == ["a+b c"]

    def test_지역_값에_특수문자가_있으면_페이저_링크에_추가_쿼리_파라미터로_주입되지_않도록_URL_인코딩된다(self, make_event):
        """selected_region is echoed into the pager from an unvalidated
        request.GET.getlist('region') — a value containing raw '&'/'=' must
        not be re-injected into the href as extra query parameters."""
        for i in range(11):
            make_event(title=f"서울 행사 {i}", region="seoul")
        malicious_region = "a&status=closed"

        resp = Client().get("/events/", {"region": ["seoul", malicious_region]})

        assert resp.status_code == 200
        body = resp.content.decode()
        assert f"region={quote(malicious_region)}" in body
        assert f"region={malicious_region}" not in body


@pytest.mark.django_db
class TestEventListSortMenu:
    """정렬은 2026-07-22부터 사이드바 <select>가 아니라 결과 헤더 우측 상단의
    토글 메뉴로 조작한다. 메뉴 항목은 링크이므로 정렬을 바꿀 때 현재 필터가
    쿼리스트링으로 함께 실려야 한다 — 그게 이 계층이 지킬 계약이다."""

    def test_정렬_메뉴는_모든_정렬_항목을_현재_필터를_유지한_링크로_제공한다(self, make_event):
        make_event(title="정렬메뉴필터유지행사", region="seoul")

        resp = Client().get("/events/", {"region": "seoul", "q": "정렬메뉴"})

        assert resp.status_code == 200
        body = resp.content.decode()
        menu = re.search(
            r'<ul[^>]*class="results-sort-menu"[^>]*>(.*?)</ul>', body, re.DOTALL
        )
        assert menu, "결과 헤더에 정렬 메뉴가 렌더링되지 않음"

        hrefs = re.findall(r'href="([^"]+)"', menu.group(1))
        sort_values = []
        for href in hrefs:
            params = parse_qs(
                urlparse(unescape(href)).query, keep_blank_values=True
            )
            assert params.get("region") == ["seoul"], f"{href}: 지역 필터 유실"
            assert params.get("q") == ["정렬메뉴"], f"{href}: 검색어 유실"
            sort_values.append(params.get("sort", [""])[0])

        assert sort_values == [slug for slug, _label in EVENT_SORT]

    def test_선택된_정렬_항목만_현재_항목으로_표시된다(self, make_event):
        make_event(title="정렬메뉴선택표시행사")

        resp = Client().get("/events/", {"sort": "closing_soon"})

        assert resp.status_code == 200
        body = resp.content.decode()
        menu = re.search(
            r'<ul[^>]*class="results-sort-menu"[^>]*>(.*?)</ul>', body, re.DOTALL
        )
        assert menu
        current = re.findall(
            r'<a[^>]*aria-current="true"[^>]*>([^<]+)</a>', menu.group(1)
        )
        assert current == [EVENT_SORT_LABELS["closing_soon"]]

    def test_사이드바_필터_폼에는_정렬_선택_상자가_남아있지_않다(self, make_event):
        make_event(title="정렬셀렉트제거행사")

        resp = Client().get("/events/")

        assert resp.status_code == 200
        assert '<select name="sort"' not in resp.content.decode()


@pytest.mark.django_db
def test_비공개_직접_등록_항목은_공개_행사_목록_페이지에_노출되지_않는다(client, make_user):
    """A private PersonalEntry item must not leak into the public browse page
    HTML (split from archive's test_personal_entry_never_appears_in_public_catalog
    — the API half stays in tests/archive/test_personal_entries_api.py).

    Uses PersonalEntry.objects.create directly rather than archive's make_entry
    fixture: that fixture lives in tests/archive/conftest.py, which pytest's
    per-directory conftest scoping does not expose here in tests/events/.
    """
    from archive.models import PersonalEntry

    user = make_user(username="pe-leak")
    PersonalEntry.objects.create(user=user, kind="place", title="PRIVATE_LEAK_CANARY")

    client.force_login(user)
    browse = client.get("/events/")

    assert browse.status_code == 200
    assert "PRIVATE_LEAK_CANARY" not in browse.content.decode()
