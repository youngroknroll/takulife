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

pytestmark = pytest.mark.web

# (url, full_template, fragment_template) for each search-enabled archive page.
ARCHIVE_PAGES = [
    ("/archive/", "core/archive/index.html", "core/partials/_archive_results_record.html"),
    ("/archive/statuses/", "core/archive/statuses.html", "core/partials/_archive_results_statuses.html"),
    ("/archive/visits/", "core/archive/visits.html", "core/partials/_archive_results_visits.html"),
    ("/archive/items/", "core/archive/personal_entries.html", "core/partials/_archive_results_personal.html"),
]
ARCHIVE_PAGE_IDS = ["전체_보기", "나의_일정", "다녀온_기록", "직접_등록"]


def _template_names(resp):
    return {t.name for t in resp.templates if t.name}


@pytest.mark.django_db
class TestArchivePartialBranch:
    @pytest.mark.parametrize(
        "url,full_template,fragment_template", ARCHIVE_PAGES, ids=ARCHIVE_PAGE_IDS
    )
    def test_partial_1로_요청하면_결과_조각만_응답한다(
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

    @pytest.mark.parametrize(
        "url,full_template,fragment_template", ARCHIVE_PAGES, ids=ARCHIVE_PAGE_IDS
    )
    def test_일반_요청은_전체_페이지를_그대로_렌더링한다(self, user_client, url, full_template, fragment_template):
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

    @pytest.mark.parametrize(
        "url,full_template,fragment_template", ARCHIVE_PAGES, ids=ARCHIVE_PAGE_IDS
    )
    def test_비로그인_사용자의_partial_요청은_로그인_페이지로_리다이렉트된다(self, url, full_template, fragment_template):
        client = Client()  # anonymous

        resp = client.get(url + "?partial=1")

        # @login_required still applies to the partial branch.
        assert resp.status_code == 302
        assert "/accounts/login/" in resp["Location"]

    @pytest.mark.parametrize(
        "url,full_template,fragment_template", ARCHIVE_PAGES, ids=ARCHIVE_PAGE_IDS
    )
    @pytest.mark.parametrize(
        "bad_partial",
        ["", "0", "2", "true", "yes", "01"],
        ids=["빈_문자열", "값_0", "값_2", "문자열_true", "문자열_yes", "0으로_시작하는_01"],
    )
    def test_partial_값이_1이_아니면_전체_페이지로_대체_응답한다(
        self, user_client, url, full_template, fragment_template, bad_partial
    ):
        _user, client = user_client()

        resp = client.get(f"{url}?partial={bad_partial}")

        assert resp.status_code == 200
        names = _template_names(resp)
        assert full_template in names
        assert "base.html" in names

    def test_전체_보기_partial_렌더링에_검색어를_적용하면_일치하는_행사만_응답한다(self, user_client, make_event, make_status):
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

    def test_전체_보기에서_검색어_없이_상태_필터만_적용해_일치하는_행이_없으면_상태별_빈_안내문구를_보여준다(self, user_client, make_event, make_status):
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

    def test_나의_일정_partial_렌더링이_페이지를_넘으면_partial_없는_페이저_링크를_포함한다(self, user_client, make_event, make_status):
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

    def test_나의_일정_partial_렌더링에_검색어를_적용하면_일치하는_행사만_응답한다(self, user_client, make_event, make_status):
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

    def test_다녀온_기록_partial_렌더링에_검색어를_적용하면_일치하는_행사만_응답한다(self, user_client, make_event, make_visit):
        user, client = user_client()
        match = make_event(title="방문 매칭")
        other = make_event(title="방문 제외")
        make_visit(user, event=match, visited_on="2026-01-01")
        make_visit(user, event=other, visited_on="2026-01-02")

        resp = client.get("/archive/visits/?q=매칭&partial=1")

        assert resp.status_code == 200
        assert "방문 매칭".encode() in resp.content
        assert "방문 제외".encode() not in resp.content

    def test_직접_등록_partial_렌더링에_검색어를_적용하면_일치하는_항목만_응답한다(self, user_client, make_entry):
        user, client = user_client()
        make_entry(user, kind=PersonalEntry.Kind.PLACE, title="매칭 카페")
        make_entry(user, kind=PersonalEntry.Kind.PLACE, title="제외 장소")

        resp = client.get("/archive/items/?q=매칭&partial=1")

        assert resp.status_code == 200
        assert "매칭 카페".encode() in resp.content
        assert "제외 장소".encode() not in resp.content

    def test_직접_등록_목록에서_굿즈_항목은_찜_상태_승격_액션은_없고_삭제만_가능하다(self, user_client, make_entry):
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
