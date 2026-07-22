"""Events calendar SSR view (dual-calendar Test List §단계 5, Events 분):
CAL-5-02~5-11 excluding CAL-5-01 (Activity-only, next round).

`GET /events/calendar/` does not exist yet (config/urls.py has no
`event-calendar-page` route) — every test below is expected to fail with a
404 (Resolver404 at the Django test-client level, i.e. `response.status_code
== 404`, not a 200/assertion mismatch) until the SSR view and route are
added. This is a different Red shape from the §단계 3/4 files (those failed
at collection with ImportError): this file's tests all collect fine, they
fail at *assertion* time on the very first `assert resp.status_code == 200`.

Assumed web-layer contract (fixed only to the extent the coordinator's
message specified; concrete template/markup is the implementer's choice):
- Query params: `month=YYYY-MM` (absent → today's month, `timezone.localdate()`
  read the same way core.views.home/event_list already do — see
  tests/events/test_home_view.py's `patch("core.views.timezone.localdate",
  ...)` convention, reused here), `date=YYYY-MM-DD` (absent → the CAL-4-04/05
  default-selection rule), plus the existing q/region/category/status
  filters (same param names as `/events/`).
- Invalid month/date (parse failure, out-of-range, nonexistent date, or a
  date outside the displayed month) → HTTP 200 with an inline error panel
  containing the exact copy the Web Experience Designer fixed
  (frontend pre-review §A-13): title "요청한 날짜를 확인할 수 없어요" and an
  "이번 달 보기" recovery link whose href drops every invalid param.
- A month-query failure (exception raised inside the view's query call) →
  HTTP 200 with an inline error + retry cue, never 500. Retry copy
  (templates/core/events/calendar.html, now built): note "잠시 후 다시
  시도해 주세요.", recovery link text "다시 시도" — asserted below via the
  "다시 시도" substring (previously "재시도", flagged as provisional pending
  the actual template; now confirmed).
- Valid extreme months (0001-01, 9999-12) render normally (no error panel),
  with the selected date's own empty-state copy when there is no data
  (service design §9.4: "이 날짜에는 등록된 공식 행사가 없어요").
- List↔calendar toggle links: confirmed via the actual templates —
  `<nav class="nav-links">` on templates/core/events/list.html and
  `<nav class="nav-links calendar-page-toggle">` on
  templates/core/events/calendar.html, each containing exactly the 목록/달력
  anchor pair, querystring-preserving (`?{{ request.GET.urlencode }}`).
  Extraction below is scoped to that `<nav>` block specifically — the page
  also renders the site's global header nav (templates/core/partials/
  _site_header.html), whose own plain `href="/events/"` link would
  otherwise be matched first by an unscoped page-wide search.
- Month-nav links (previous/next): confirmed via
  templates/core/events/calendar.html's `<nav class="calendar-month-nav">`,
  rendered as page-relative `href="?month=...{{ extra_query }}"` (no leading
  path — a browser resolves this against the current page, but Django's
  test Client needs an absolute path, so tests below re-prefix it with
  `/events/calendar/` before following it). Extraction is scoped to that
  `<nav>` specifically — the day-cell grid (templates/core/partials/
  _calendar_grid.html) also emits `href="?month=...&date=...#selected-date"`
  links for every visible day (including adjacent-month filler days), which
  an unscoped search could otherwise match instead of the intended
  previous/next control. Filter-preservation is verified via the
  destination page's own filter-checkbox `checked` state (existing
  `filter-check` markup, templates/core/events/list.html /
  templates/core/events/calendar.html), using `region="seoul"`, a real
  slug from core.vocab.REGION.
- The selected date's event(s) appear by title; an event on a different day
  within the same displayed month does not (CAL-5-04/5-11). Assertions are
  scoped to the response body *after* `id="selected-date"`
  (templates/core/events/calendar.html's `<section ... id="selected-date">`)
  — the month grid itself also renders each day's event titles in its own
  cell (templates/core/partials/_calendar_grid.html's `.day-item` spans), so
  an unscoped whole-body search would find the "other day" event's title
  too (in its own grid cell), even though it correctly does not appear in
  the selected-date detail list.
- CAL-5-09/5-10 call the pre-existing EventInterest/UserEventStatus JSON
  APIs directly (not a calendar-specific endpoint) — these two may already
  be green today, since those APIs predate this page; they exist to pin the
  "calendar quick actions reuse the existing public contract, no new
  endpoint" premise for CAL-5-09/5-10, not to test new behavior.
"""
import html
import re
from datetime import date
from unittest.mock import patch

import pytest
from django.test import Client

pytestmark = pytest.mark.web


def _extract_href(body, link_text):
    match = re.search(
        rf'<a[^>]*href="([^"]*)"[^>]*>\s*{re.escape(link_text)}\s*</a>', body
    )
    assert match, f"{link_text!r} 링크를 찾을 수 없음"
    # `href="?{{ extra_query }}"` is a Django-autoescaped variable
    # substitution, so a literal '&' inside extra_query's value is rendered
    # as the HTML entity '&amp;' in the response bytes — a real browser
    # decodes that back to '&' before using the href as a URL; unescape
    # here so this test does the same instead of feeding a literal
    # "&amp;"-containing string to Client().get().
    return html.unescape(match.group(1))


def _extract_nav_hrefs(body, nav_class):
    """Return every href inside the first <nav class="{nav_class}..."> block
    — scopes extraction to a specific nav instead of the whole page, so an
    unrelated link elsewhere (e.g. the global site header's own /events/
    link, or the day-cell grid's own ?month=... links) is never picked up
    by accident. Hrefs are HTML-unescaped (see _extract_href's comment)."""
    match = re.search(
        rf'<nav[^>]*class="{re.escape(nav_class)}[^"]*"[^>]*>(.*?)</nav>',
        body,
        re.DOTALL,
    )
    assert match, f'<nav class="{nav_class}..."> 컨테이너를 찾을 수 없음'
    return [html.unescape(href) for href in re.findall(r'href="([^"]*)"', match.group(1))]


def _first_containing(hrefs, needle):
    for href in hrefs:
        if needle in href:
            return href
    return None


def _as_absolute(href, *, base_path):
    """Some nav links are emitted as page-relative query-only hrefs (e.g.
    '?month=2026-08&region=seoul') — a browser resolves that against the
    current page's own path, but Django's test Client takes the given
    string as a literal path, so prefix it with the current page's path
    first when the href itself has none."""
    if href.startswith("?"):
        return base_path + href
    return href


def _selected_date_section(body):
    """Return the response body from `id="selected-date"` onward — scopes
    CAL-5-04/5-11's title presence/absence checks to the selected-date
    detail section, since the month grid also renders event titles in its
    own day cells (see module docstring)."""
    marker = 'id="selected-date"'
    index = body.find(marker)
    assert index != -1, f"{marker!r} 섹션을 찾을 수 없음"
    return body[index:]


# ---------------------------------------------------------------------------
# CAL-5-02 — list↔calendar toggle preserves the filter querystring
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_목록에서_달력으로_전환해도_지역_필터가_유지된다():
    list_resp = Client().get("/events/", {"region": "seoul"})
    assert list_resp.status_code == 200
    list_body = list_resp.content.decode()

    # 목록 페이지는 2026-07-22 에디토리얼 리빌드에서 전환 탭을 nav-links(알약)
    # 대신 events-tabs(밑줄 탭)로 바꿨다. 달력 페이지는 nav-links 그대로.
    list_toggle_hrefs = _extract_nav_hrefs(list_body, "events-tabs")
    calendar_href = _first_containing(list_toggle_hrefs, "/events/calendar/")
    assert calendar_href is not None, "목록 페이지 events-tabs에 달력 전환 링크가 없음"
    assert "region=seoul" in calendar_href

    calendar_resp = Client().get(_as_absolute(calendar_href, base_path="/events/"))
    assert calendar_resp.status_code == 200
    calendar_body = calendar_resp.content.decode()

    calendar_toggle_hrefs = _extract_nav_hrefs(calendar_body, "nav-links")
    list_href = _first_containing(calendar_toggle_hrefs, "/events/?")
    assert list_href is not None, "달력 페이지 nav-links에 목록 전환 링크가 없음"
    assert "region=seoul" in list_href


# ---------------------------------------------------------------------------
# CAL-5-03 — month navigation preserves the filter querystring
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_다음_달로_이동해도_기존_필터가_유지된다(make_event):
    make_event(
        title="필터유지월이동테스트행사",
        region="seoul",
        start_date=date(2026, 7, 10),
        end_date=date(2026, 7, 10),
    )

    resp = Client().get("/events/calendar/", {"month": "2026-07", "region": "seoul"})
    assert resp.status_code == 200
    body = resp.content.decode()

    month_nav_hrefs = _extract_nav_hrefs(body, "calendar-month-nav")
    next_month_href = _first_containing(month_nav_hrefs, "month=2026-08")
    assert next_month_href is not None, "calendar-month-nav에 다음 달 링크가 없음"
    assert "region=seoul" in next_month_href

    next_resp = Client().get(_as_absolute(next_month_href, base_path="/events/calendar/"))
    assert next_resp.status_code == 200
    next_body = next_resp.content.decode()
    assert re.search(r'name="region"\s+value="seoul"[^>]*checked', next_body)


# ---------------------------------------------------------------------------
# CAL-5-04 — the detail list shows only the selected date's events
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_날짜를_선택하면_그_날짜에_진행되는_행사만_상세_목록에_표시된다(make_event):
    selected_title = "캘린더상세목록전용선택행사타이틀123"
    other_day_title = "캘린더상세목록전용다른날짜행사타이틀456"
    make_event(title=selected_title, start_date=date(2026, 7, 10), end_date=date(2026, 7, 10))
    make_event(title=other_day_title, start_date=date(2026, 7, 20), end_date=date(2026, 7, 20))

    resp = Client().get("/events/calendar/", {"month": "2026-07", "date": "2026-07-10"})

    assert resp.status_code == 200
    detail_section = _selected_date_section(resp.content.decode())
    assert selected_title in detail_section
    assert other_day_title not in detail_section


# ---------------------------------------------------------------------------
# CAL-5-05 — month absent defaults to today's month, no error
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_month_파라미터가_없으면_오류_없이_당월이_표시된다(make_event):
    fixed_today = date(2026, 7, 19)
    make_event(title="당월기본표시행사", start_date=fixed_today, end_date=fixed_today)

    with patch("core.views.timezone.localdate", return_value=fixed_today):
        resp = Client().get("/events/calendar/")

    assert resp.status_code == 200
    body = resp.content.decode()
    assert "요청한 날짜를 확인할 수 없어요" not in body
    assert "당월기본표시행사" in body


# ---------------------------------------------------------------------------
# CAL-5-06 — invalid month/date → 200 + inline error panel + recovery link
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "query_params, invalid_value",
    [
        ({"month": "abc"}, "abc"),
        ({"month": "2026-13"}, "2026-13"),
        ({"month": ""}, None),
        ({"month": "2026-07", "date": "not-a-date"}, "not-a-date"),
        ({"month": "2026-02", "date": "2026-02-30"}, "2026-02-30"),
        ({"month": "2026-07", "date": "2026-08-15"}, "2026-08-15"),
    ],
    ids=[
        "month_문자열",
        "month_13월",
        "month_빈값",
        "date_형식오류",
        "date_존재하지_않는_날짜",
        "date_표시월_밖",
    ],
)
def test_잘못된_month_date_입력은_200과_함께_인라인_오류_패널로_처리된다(
    query_params, invalid_value
):
    resp = Client().get("/events/calendar/", query_params)

    assert resp.status_code == 200
    body = resp.content.decode()
    assert "요청한 날짜를 확인할 수 없어요" in body

    href = _extract_href(body, "이번 달 보기")
    if invalid_value is not None:
        assert invalid_value not in href
    else:
        # "month=" 빈 값 케이스: 빈 값 그대로가 복구 링크에 남아있지 않아야 한다.
        assert "month=&" not in href
        assert not href.endswith("month=")


# ---------------------------------------------------------------------------
# CAL-5-07 — valid extreme months render without clamping
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "month_param",
    ["0001-01", "9999-12"],
    ids=["매우_이른_월", "매우_늦은_월"],
)
def test_유효한_극단적_월은_클램프_없이_그대로_렌더링된다(month_param):
    resp = Client().get("/events/calendar/", {"month": month_param})

    assert resp.status_code == 200
    body = resp.content.decode()
    assert "요청한 날짜를 확인할 수 없어요" not in body
    assert "이 날짜에는 등록된 공식 행사가 없어요" in body


# ---------------------------------------------------------------------------
# CAL-5-08 — a month-query failure degrades to an error panel, never 500
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_월_조회가_실패하면_500대신_오류_패널과_재시도_안내가_표시된다(monkeypatch):
    def _raise(*args, **kwargs):
        raise RuntimeError("월 조회 실패 주입")

    monkeypatch.setattr("core.views.list_published_events_for_month", _raise)

    resp = Client().get("/events/calendar/")

    assert resp.status_code == 200
    assert "다시 시도" in resp.content.decode()


# ---------------------------------------------------------------------------
# CAL-5-09/5-10 — calendar quick actions reuse the existing public API
# contract verbatim (premise recheck; may already be green today — see
# module docstring).
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_행사_달력_날짜_상세에서_찜_추가_요청이_기존_공개_계약대로_처리된다(
    client, make_user, make_event
):
    user = make_user(username="cal-event-interest-quick-action")
    event = make_event(title="달력 날짜 상세 찜 대상 행사")

    client.force_login(user)
    response = client.post(
        "/api/event-interests/",
        {"event": event.id},
        content_type="application/json",
    )

    assert response.status_code == 201


@pytest.mark.django_db
def test_행사_달력_날짜_상세에서_방문_예정_등록_요청이_기존_공개_계약대로_처리된다(
    client, make_user, make_event
):
    user = make_user(username="cal-event-status-quick-action")
    event = make_event(title="달력 날짜 상세 방문예정 대상 행사")

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 201


# ---------------------------------------------------------------------------
# CAL-5-11 — a multi-day event appears in the detail list for any day in
# its run, not only its start date
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "selected_date",
    ["2026-07-05", "2026-07-06", "2026-07-07"],
    ids=["시작일", "중간일", "종료일"],
)
def test_여러_날_진행되는_행사를_아무_날짜로_선택해도_상세_목록에_나타난다(
    make_event, selected_date
):
    title = "다일진행행사캘린더상세타이틀789"
    make_event(title=title, start_date=date(2026, 7, 5), end_date=date(2026, 7, 7))

    resp = Client().get("/events/calendar/", {"month": "2026-07", "date": selected_date})

    assert resp.status_code == 200
    assert title in _selected_date_section(resp.content.decode())


# ---------------------------------------------------------------------------
# CALFIX-1 — active_filter_count is exposed in context (calendar review fixes
# plan .docs/plans/2026-07-19-calendar-review-fixes-plan.md 단계 1)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "query_params, expected_count",
    [
        ({"region": "seoul", "q": "포스터"}, 2),
        ({}, 0),
    ],
    ids=["지역과_검색어_2개", "무필터_0개"],
)
def test_행사_달력을_필터와_함께_조회하면_활성_필터_개수가_컨텍스트에_담긴다(
    query_params, expected_count
):
    resp = Client().get("/events/calendar/", query_params)

    assert resp.status_code == 200
    assert resp.context["active_filter_count"] == expected_count


# ---------------------------------------------------------------------------
# CAL-EDIT-1 — active_filter_chips is exposed in context, same derivation as
# event_list (편집 계획 §D)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_필터가_적용된_달력_요청의_컨텍스트에_적용_필터_칩이_담긴다():
    resp = Client().get("/events/calendar/", {"region": "seoul", "q": "포스터"})

    assert resp.status_code == 200
    chips = resp.context["active_filter_chips"]
    assert "검색: 포스터" in chips
    assert any("서울" in chip for chip in chips)


# ---------------------------------------------------------------------------
# CAL-EDIT-2 — weeks[].items[] carries category_slug for date-cell category
# bars/dots (편집 계획 §D)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_달력_주_항목에_카테고리_슬러그가_담긴다(make_event):
    make_event(
        title="카테고리슬러그테스트행사",
        category="goods-sale",
        start_date=date(2026, 7, 10),
        end_date=date(2026, 7, 10),
    )

    resp = Client().get("/events/calendar/", {"month": "2026-07"})

    assert resp.status_code == 200
    weeks = resp.context["weeks"]
    matching_items = [
        item
        for week in weeks
        for cell in week
        if cell["date"] == date(2026, 7, 10)
        for item in cell["items"]
    ]
    assert matching_items
    assert all(item["category_slug"] == "goods-sale" for item in matching_items)
