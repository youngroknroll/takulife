"""Tests for the ?partial=1 fragment branch on the four archive list pages.

Behavior under test:
- ?partial=1 returns only the results fragment (list + empty states + pager),
  not the full HTML document — the live-search JS swaps this into #archive-results.
- The fragment template is rendered (base.html is NOT in the template chain).
- A normal request (no partial) still renders the full page unchanged.
- The partial branch keeps the view's @login_required gate — an anonymous
  ?partial=1 request redirects to login, never leaks a fragment.
- The partial branch applies the same q filter as the full page.
- partial values other than "1" fall back to the full page (no fragment leak).
"""
import pytest
from django.test import Client

from archive.models import PersonalEntry

# (url, full_template, fragment_template) for each search-enabled archive page.
ARCHIVE_PAGES = [
    ("/archive/", "core/archive/index.html", "core/partials/_archive_results_record.html"),
    ("/archive/statuses/", "core/archive/statuses.html", "core/partials/_archive_results_statuses.html"),
    ("/archive/visits/", "core/archive/visits.html", "core/partials/_archive_results_visits.html"),
    ("/archive/items/", "core/archive/personal_entries.html", "core/partials/_archive_results_personal.html"),
]


def _template_names(resp):
    return {t.name for t in resp.templates if t.name}


@pytest.mark.django_db
class TestArchivePartialBranch:
    @pytest.mark.parametrize("url,full_template,fragment_template", ARCHIVE_PAGES)
    def test_partial_renders_fragment_only(
        self, user_client, url, full_template, fragment_template
    ):
        _user, client = user_client()

        resp = client.get(url + "?partial=1")

        assert resp.status_code == 200
        names = _template_names(resp)
        assert fragment_template in names
        # The fragment must NOT drag in the full page chrome.
        assert full_template not in names
        assert "base.html" not in names
        # No document shell, and no swap wrapper (that lives in the full page).
        assert b"<html" not in resp.content.lower()
        assert b'id="archive-results"' not in resp.content

    @pytest.mark.parametrize("url,full_template,fragment_template", ARCHIVE_PAGES)
    def test_full_page_unchanged(self, user_client, url, full_template, fragment_template):
        _user, client = user_client()

        resp = client.get(url)

        assert resp.status_code == 200
        names = _template_names(resp)
        assert full_template in names
        assert "base.html" in names
        # Full page wraps the fragment in the swap target and includes it.
        assert fragment_template in names
        assert b'id="archive-results"' in resp.content
        assert b"<html" in resp.content.lower()

    @pytest.mark.parametrize("url,full_template,fragment_template", ARCHIVE_PAGES)
    def test_partial_requires_login(self, url, full_template, fragment_template):
        client = Client()  # anonymous

        resp = client.get(url + "?partial=1")

        # @login_required still applies to the partial branch.
        assert resp.status_code == 302
        assert "/accounts/login/" in resp["Location"]

    @pytest.mark.parametrize("url,full_template,fragment_template", ARCHIVE_PAGES)
    @pytest.mark.parametrize("bad_partial", ["", "0", "2", "true", "yes", "01"])
    def test_non_one_partial_falls_back_to_full_page(
        self, user_client, url, full_template, fragment_template, bad_partial
    ):
        _user, client = user_client()

        resp = client.get(f"{url}?partial={bad_partial}")

        assert resp.status_code == 200
        names = _template_names(resp)
        assert full_template in names
        assert "base.html" in names

    def test_partial_applies_q_filter_on_archive_dashboard(self, user_client, make_event, make_status):
        # The /archive/ dashboard shares _archive_status_context with statuses but
        # renders the record fragment at a different page size — cover it directly.
        user, client = user_client()
        match = make_event(title="매칭 이벤트", location_name="서울")
        other = make_event(title="다른 이벤트", location_name="부산")
        make_status(user, event=match, status="planned")
        make_status(user, event=other, status="planned")

        resp = client.get("/archive/?q=매칭&partial=1")

        assert resp.status_code == 200
        titles = [row["subject"]["title"] for row in resp.context["status_rows"]]
        assert "매칭 이벤트" in titles
        assert "다른 이벤트" not in titles
        assert "매칭 이벤트".encode() in resp.content
        assert "다른 이벤트".encode() not in resp.content

    def test_partial_status_filter_with_no_q_match_shows_empty_on_dashboard(self, user_client, make_event, make_status):
        # has_any=True, active status filter matches zero rows, no query → the
        # record fragment's `elif has_any` notice branch (not the search-empty one).
        user, client = user_client()
        planned = make_event(title="예정 행사")
        make_status(user, event=planned, status="planned")

        resp = client.get("/archive/?status=missed&partial=1")

        assert resp.status_code == 200
        assert resp.context["has_any"] is True
        assert resp.context["has_statuses"] is False
        assert "예정 행사".encode() not in resp.content
        assert "이 상태로 저장한 행사가 없습니다".encode() in resp.content

    def test_partial_renders_pager(self, user_client, make_event, make_status):
        # More records than one page → the pager must render inside the fragment,
        # and its links must never carry partial= (else a click would navigate to
        # a chrome-less fragment). /archive/statuses/ paginates at 5 per page.
        user, client = user_client()
        for i in range(7):  # > ARCHIVE_STATUS_PAGE_SIZE (5) → 2 pages
            ev = make_event(title=f"행사 {i}")
            make_status(user, event=ev, status="planned")

        resp = client.get("/archive/statuses/?partial=1")

        assert resp.status_code == 200
        assert resp.context["page_obj"].has_next()
        assert b'class="pager"' in resp.content
        assert b"partial=" not in resp.content

    def test_partial_applies_q_filter_on_statuses(self, user_client, make_event, make_status):
        user, client = user_client()
        match = make_event(title="매칭 이벤트", location_name="서울")
        other = make_event(title="다른 이벤트", location_name="부산")
        make_status(user, event=match, status="planned")
        make_status(user, event=other, status="planned")

        resp = client.get("/archive/statuses/?q=매칭&partial=1")

        assert resp.status_code == 200
        titles = [row["subject"]["title"] for row in resp.context["status_rows"]]
        assert "매칭 이벤트" in titles
        assert "다른 이벤트" not in titles
        # And the rendered fragment reflects the filter.
        assert "매칭 이벤트".encode() in resp.content
        assert "다른 이벤트".encode() not in resp.content

    def test_partial_applies_q_filter_on_visits(self, user_client, make_event, make_visit):
        user, client = user_client()
        match = make_event(title="방문 매칭")
        other = make_event(title="방문 제외")
        make_visit(user, event=match, visited_on="2026-01-01")
        make_visit(user, event=other, visited_on="2026-01-02")

        resp = client.get("/archive/visits/?q=매칭&partial=1")

        assert resp.status_code == 200
        assert "방문 매칭".encode() in resp.content
        assert "방문 제외".encode() not in resp.content

    def test_partial_applies_q_filter_on_items(self, user_client, make_entry):
        user, client = user_client()
        make_entry(user, kind=PersonalEntry.Kind.PLACE, title="매칭 카페")
        make_entry(user, kind=PersonalEntry.Kind.PLACE, title="제외 장소")

        resp = client.get("/archive/items/?q=매칭&partial=1")

        assert resp.status_code == 200
        assert "매칭 카페".encode() in resp.content
        assert "제외 장소".encode() not in resp.content

    def test_items_page_hides_actions_on_goods_rows(self, user_client, make_entry):
        # GOODS is no longer a valid interest/status/promotion subject
        # (collection domain plan §3-3, gate M1: goods are unreachable via
        # every UI path once C2 merges) — its row must render with no
        # interest/status buttons and no 공식 제보 form, while a place row
        # keeps them.
        user, client = user_client()
        make_entry(user, kind=PersonalEntry.Kind.PLACE, title="장소 항목")
        make_entry(user, kind="goods", title="굿즈 항목")

        resp = client.get("/archive/items/")

        assert resp.status_code == 200
        content = resp.content
        assert b"data-interest-toggle" in content
        assert b"data-status-action" in content
        assert b"data-promote-toggle" in content

        rows = {row["entry"].title: row for row in resp.context["entry_rows"]}
        place_id = rows["장소 항목"]["entry"].id
        goods_id = rows["굿즈 항목"]["entry"].id
        assert f'data-personal-entry-id="{goods_id}"'.encode() not in content
        assert f'data-promote-toggle="{goods_id}"'.encode() not in content
        assert f'data-personal-entry-id="{place_id}"'.encode() in content
        # Delete is not restricted by the plan (only status/visit/interest/
        # promotion are) — a goods row must still offer a way to remove
        # itself during the transitional period before it migrates to
        # CollectionItem (C4).
        assert f'data-delete-entry-id="{goods_id}"'.encode() in content
