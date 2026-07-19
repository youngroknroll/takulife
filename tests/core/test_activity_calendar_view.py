"""Activity calendar SSR view (dual-calendar Test List §단계 5, Activity 분):
CAL-5-01 + newly-discovered CAL-5-12~16 (recorded in
.docs/plans/2026-07-19-dual-calendar-test-list.md per its own "신규 발견
시나리오는 이 문서에 추가한다" convention).

`GET /archive/calendar/` does not exist yet (config/urls.py has no
`archive-calendar-page` route) — every test below is expected to fail with
a 404 at the very first status-code assertion, before the view/route is
added. This includes CAL-5-01 (anonymous access): URL resolution happens
before `login_required` ever runs, so an anonymous request to a
not-yet-registered path also 404s rather than 302s — the assertion
`resp.status_code == 302` will fail against an actual 404, which is still a
correct Red for a route that doesn't exist (mirrors PR-C's
test_events_calendar_view.py's documented Red shape).

Assumed web-layer contract for the Activity calendar (proposed here per
the coordinator's message; confirmed/adjusted with the Backend TDD Coach at
Green time, same as PR-C's provisional-then-confirmed contract):
- `GET /archive/calendar/`, name="archive-calendar-page", `@login_required`
  (mirrors every other `archive/*` view in core/views.py).
- Query params: `month=YYYY-MM`/`date=YYYY-MM-DD` — identical parsing rules
  to the Events calendar (service design §11.1: absent vs blank-but-present
  distinction, invalid → `calendar_error="invalid"`). `type=` is a repeated
  param selecting a subset of 5 groups: `schedule`/`interest`/`status`/
  `visit`/`goods`, each mapping to the archive.queries kind constants
  (schedule→SCHEDULE_KIND, interest→INTEREST_ADDED/REMOVED + the §7.5
  legacy-찜 fallback, status→STATUS_CHANGED/REMOVED, visit→VISIT_KIND +
  VISIT_RECORD_CREATED, goods→GOODS_ACQUIRED_KIND +
  COLLECTION_ITEM_CREATED/ORGANIZED).
- Selected-date detail section: `id="selected-date"` (same convention as
  Events calendar.html), sliced via `_selected_date_section` below — the
  month grid also renders each day's item labels in its own cell
  (PR-C's day-cell title-collision lesson applies identically here), so
  every presence/absence assertion below is scoped to this section, never
  the raw whole-body text.
- Month-nav links: `<nav class="calendar-month-nav">` (same class as
  Events calendar.html), preserving `type=` the same way Events preserves
  region/category/status/q via `extra_query`.
- Empty state when the whole displayed month has zero activity: the
  existing dual-CTA pattern already used elsewhere in this exact codebase
  (templates/core/partials/_home_collection_snapshot.html's
  `<div class="empty-actions"><a href="/events/">행사 찾기</a>
  <a href="/collection/new/">굿즈 등록</a></div>`, service design §9.4) —
  assumed reused verbatim rather than a new pattern. Copy text itself is
  not yet confirmed by WED (per the coordinator's note), so only the two
  hrefs are asserted, not the link text.
- Invalid-month error panel: identical copy to the Events calendar
  (frontend pre-review §A-13) — "요청한 날짜를 확인할 수 없어요" title,
  "이번 달 보기" recovery link — since both pages are expected to reuse the
  same parsing helpers and error-panel markup per the coordinator's note.
"""
import html
import re
from datetime import date
from urllib.parse import parse_qs, urlparse

import pytest
from django.test import Client

from archive.models import CollectionItem, UserEventStatus, VisitRecord

pytestmark = pytest.mark.web


def _extract_href(body, link_text):
    match = re.search(
        rf'<a[^>]*href="([^"]*)"[^>]*>\s*{re.escape(link_text)}\s*</a>', body
    )
    assert match, f"{link_text!r} 링크를 찾을 수 없음"
    return html.unescape(match.group(1))


def _extract_block(body, *, tag, class_prefix):
    """Return the inner HTML of the first <{tag} class="{class_prefix}...">
    ... </{tag}> block — scopes extraction to a specific container instead
    of the whole page (PR-C's test_events_calendar_view.py established this
    pattern after discovering an unscoped page-wide search can match an
    unrelated link, e.g. the global site header's own /events/ link)."""
    match = re.search(
        rf'<{tag}[^>]*class="{re.escape(class_prefix)}[^"]*"[^>]*>(.*?)</{tag}>',
        body,
        re.DOTALL,
    )
    assert match, f'<{tag} class="{class_prefix}..."> 컨테이너를 찾을 수 없음'
    return match.group(1)


def _extract_nav_hrefs(body, nav_class):
    return [
        html.unescape(href)
        for href in re.findall(r'href="([^"]*)"', _extract_block(body, tag="nav", class_prefix=nav_class))
    ]


def _first_containing(hrefs, needle):
    for href in hrefs:
        if needle in href:
            return href
    return None


def _selected_date_section(body):
    """Return the response body from `id="selected-date"` onward — scopes
    item presence/absence checks to the selected-date detail section, since
    the month grid also renders each day's item labels in its own cell
    (see module docstring)."""
    marker = 'id="selected-date"'
    index = body.find(marker)
    assert index != -1, f"{marker!r} 섹션을 찾을 수 없음"
    return body[index:]


# ---------------------------------------------------------------------------
# CAL-5-01 — anonymous access redirects to login with next= preserving the
# full requested URL (including querystring)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_비로그인_사용자가_활동_달력에_접근하면_로그인으로_리다이렉트되고_next에_현재_url이_보존된다():
    resp = Client().get("/archive/calendar/", {"month": "2026-07", "date": "2026-07-10"})

    assert resp.status_code == 302
    parsed = urlparse(resp.url)
    assert parsed.path == "/accounts/login/"
    assert parse_qs(parsed.query).get("next") == [
        "/archive/calendar/?month=2026-07&date=2026-07-10"
    ]


# ---------------------------------------------------------------------------
# CAL-5-12 — only the logged-in user's own activity renders, never another
# user's
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_활동_달력에는_본인_활동만_렌더된다(user_client, make_user, make_event):
    user, client = user_client()
    other_user = make_user(username="cal-activity-other-user")
    own_event = make_event(title="본인전용달력방문행사")
    other_event = make_event(title="타인전용달력방문행사")
    VisitRecord.objects.create(user=user, event=own_event, visited_on=date(2026, 7, 10))
    VisitRecord.objects.create(user=other_user, event=other_event, visited_on=date(2026, 7, 10))

    resp = client.get("/archive/calendar/", {"month": "2026-07", "date": "2026-07-10"})

    assert resp.status_code == 200
    body = resp.content.decode()
    # Privacy leak check spans the *whole* body, not just the detail
    # section — another user's activity must never appear anywhere on the
    # page, not merely be excluded from the selected-date list.
    assert "타인전용달력방문행사" not in body
    assert "본인전용달력방문행사" in _selected_date_section(body)


# ---------------------------------------------------------------------------
# CAL-5-13 — a type= filter narrows what renders and is preserved across
# month navigation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_활동_종류_필터가_렌더에_적용되고_월_이동_링크에_보존된다(
    user_client, make_event
):
    user, client = user_client()
    scheduled_event = make_event(
        title="종류필터일정행사",
        start_date=date(2026, 7, 10),
        end_date=date(2026, 7, 10),
    )
    UserEventStatus.objects.create(
        user=user, event=scheduled_event, status=UserEventStatus.Status.PLANNED
    )
    CollectionItem.objects.create(
        user=user, name="종류필터굿즈아이템", acquired_on=date(2026, 7, 10)
    )

    resp = client.get(
        "/archive/calendar/",
        {"month": "2026-07", "date": "2026-07-10", "type": "schedule"},
    )

    assert resp.status_code == 200
    body = resp.content.decode()
    detail_section = _selected_date_section(body)
    assert "종류필터일정행사" in detail_section
    assert "종류필터굿즈아이템" not in detail_section

    month_nav_hrefs = _extract_nav_hrefs(body, "calendar-month-nav")
    next_month_href = _first_containing(month_nav_hrefs, "month=2026-08")
    assert next_month_href is not None, "calendar-month-nav에 다음 달 링크가 없음"
    assert "type=schedule" in next_month_href


# ---------------------------------------------------------------------------
# CAL-5-14 — a month with zero activity renders the dual-CTA empty state
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_기록이_전혀_없는_달은_이중_CTA_빈_상태를_렌더한다(user_client):
    _, client = user_client()

    resp = client.get("/archive/calendar/", {"month": "2026-07"})

    assert resp.status_code == 200
    empty_actions = _extract_block(resp.content.decode(), tag="div", class_prefix="empty-actions")
    hrefs = [html.unescape(href) for href in re.findall(r'href="([^"]*)"', empty_actions)]
    assert "/events/" in hrefs
    assert "/collection/new/" in hrefs


# ---------------------------------------------------------------------------
# CAL-5-15 — invalid month → 200 + inline error panel + recovery link
# (Events와 동일한 파싱 헬퍼 재사용 확인 — 대표 1케이스만)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_무효한_month_파라미터는_200과_함께_오류_패널로_처리된다(user_client):
    _, client = user_client()

    resp = client.get("/archive/calendar/", {"month": "2026-13"})

    assert resp.status_code == 200
    body = resp.content.decode()
    assert "요청한 날짜를 확인할 수 없어요" in body
    assert _extract_href(body, "이번 달 보기") is not None


# ---------------------------------------------------------------------------
# CAL-5-16 — the selected date's detail list includes only that date's
# items: an actual visit (visited_on match) and a planned event whose run
# overlaps the date, but excludes an item on a different date
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_선택_날짜_상세에는_그_날짜_항목만_방문_및_일정_겹침_포함해_표시된다(
    user_client, make_event
):
    user, client = user_client()
    scheduled_event = make_event(
        title="선택일상세일정겹침행사",
        start_date=date(2026, 7, 8),
        end_date=date(2026, 7, 12),
    )
    UserEventStatus.objects.create(
        user=user, event=scheduled_event, status=UserEventStatus.Status.PLANNED
    )
    visit_event = make_event(title="선택일상세방문행사")
    VisitRecord.objects.create(user=user, event=visit_event, visited_on=date(2026, 7, 10))
    other_day_event = make_event(title="선택일상세다른날짜행사")
    VisitRecord.objects.create(user=user, event=other_day_event, visited_on=date(2026, 7, 15))

    resp = client.get("/archive/calendar/", {"month": "2026-07", "date": "2026-07-10"})

    assert resp.status_code == 200
    detail_section = _selected_date_section(resp.content.decode())
    assert "선택일상세일정겹침행사" in detail_section
    assert "선택일상세방문행사" in detail_section
    assert "선택일상세다른날짜행사" not in detail_section
