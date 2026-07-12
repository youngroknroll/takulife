"""Tests for the public browse page view (core.views.event_list).

Behavior under test: an invalid or unmatched filter value renders the empty
state ("행사 없음"), never a hard error screen. The JSON API keeps rejecting the
same input with 400 (covered in test_events_api.py) — only the browse page
degrades gracefully.
"""
from urllib.parse import quote

import pytest
from django.test import Client


@pytest.mark.django_db
class TestEventListInvalidFilters:
    def test_invalid_status_shows_empty_state_not_error(self, make_event):
        make_event(title="Live event")

        resp = Client().get("/events/", {"status": "zzz"})

        assert resp.status_code == 200
        body = resp.content.decode()
        assert "조건에 맞는 행사가 없어요" in body
        assert "잘못된 필터 값" not in body

    def test_invalid_category_shows_empty_state(self, make_event):
        make_event(title="Live event")

        resp = Client().get("/events/", {"category": "zzz"})

        assert resp.status_code == 200
        assert "조건에 맞는 행사가 없어요" in resp.content.decode()

    def test_valid_category_filter_lists_matches(self, make_event):
        make_event(title="Popup match", category="popup_store")

        resp = Client().get("/events/", {"category": "popup_store"})

        assert resp.status_code == 200
        body = resp.content.decode()
        assert "검색 결과" in body
        assert "Popup match" in body

    def test_multiple_region_values_filter_as_or(self, make_event):
        seoul = make_event(title="Seoul one", region="seoul")
        gyeonggi = make_event(title="Gyeonggi one", region="gyeonggi")
        make_event(title="Busan one", region="busan")

        resp = Client().get("/events/?region=seoul&region=gyeonggi")

        assert resp.status_code == 200
        body = resp.content.decode()
        assert "Seoul one" in body
        assert "Gyeonggi one" in body
        assert "Busan one" not in body

    def test_sidebar_form_payload_with_blank_status_lists_matches(self, make_event):
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

    def test_authenticated_rows_reflect_user_status_and_interest(
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

    def test_row_with_region_carries_korean_label(self, make_event):
        make_event(title="서울 행사", region="seoul")

        resp = Client().get("/events/")

        row = next(r for r in resp.context["event_rows"] if r["event"].title == "서울 행사")
        assert row["region_label"] == "서울"

    def test_row_without_region_has_empty_label(self, make_event):
        make_event(title="지역 없음", region="")

        resp = Client().get("/events/")

        row = next(r for r in resp.context["event_rows"] if r["event"].title == "지역 없음")
        assert row["region_label"] == ""


@pytest.mark.django_db
class TestEventListActiveFilterChips:
    def test_query_renders_search_chip(self, make_event):
        make_event(title="공연 행사")

        resp = Client().get("/events/", {"q": "공연"})

        assert resp.status_code == 200
        assert "검색: 공연" in resp.context["active_filter_chips"]


@pytest.mark.django_db
class TestEventListPagerQEncoding:
    """The pager's ?q= link must URL-encode the search term the same way
    selected_sort already does, so a value containing '#' isn't truncated
    into a URL fragment on click, losing the rest of the query string
    (templates/core/events/list.html pager)."""

    def test_pager_link_urlencodes_q_containing_hash(self, make_event):
        for i in range(11):
            make_event(title=f"#콜라보 행사 {i}")

        resp = Client().get("/events/", {"q": "#콜라보"})

        assert resp.status_code == 200
        body = resp.content.decode()
        assert f"q={quote('#콜라보')}" in body
        assert "&q=#" not in body

    def test_pager_link_urlencodes_q_with_plus_and_space(self, make_event):
        """q="a+b c" round-trips through Django's urlencode filter, which
        quotes via urllib.parse.quote (not quote_plus) — '+' and ' ' both
        get percent-escaped, not left as literal form-encoding chars."""
        for i in range(11):
            make_event(title=f"a+b c 행사 {i}")

        resp = Client().get("/events/", {"q": "a+b c"})

        assert resp.status_code == 200
        body = resp.content.decode()
        assert f"q={quote('a+b c')}" in body
        assert "q=a+b c" not in body

    def test_pager_link_urlencodes_region_containing_special_chars(self, make_event):
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
def test_personal_entry_never_appears_in_public_browse_page(client, make_user):
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
