"""행사 달력 SSR 뷰(이중 달력 테스트 목록 §단계 5, Events 분) —
CAL-5-01(Activity 전용, 다음 회차)을 뺀 CAL-5-02~5-11.

웹 계층 계약:
- 쿼리 파라미터 `month=YYYY-MM`(부재 시 오늘의 달, core.views.home/event_list와
  같은 방식으로 `timezone.localdate()`를 읽는다 — tests/events/test_home_view.py의
  `patch("core.views.events.timezone.localdate", ...)` 관례를 재사용),
  `date=YYYY-MM-DD`(부재 시 CAL-4-04/05 기본 선택 규칙), 그리고 기존
  q/region/category/status 필터(`/events/`와 같은 파라미터명).
- 무효한 month/date(파싱 실패, 범위 밖, 존재하지 않는 날짜, 표시 월 밖 날짜)
  → HTTP 200과 함께 인라인 오류 패널, 문구는 WED가 확정한 그대로(프런트
  사전검토 §A-13): 제목 "요청한 날짜를 확인할 수 없어요", "이번 달 보기"
  복구 링크(href에서 무효 파라미터는 전부 제거).
- 월 조회 실패(뷰의 쿼리 호출 내부에서 예외 발생) → HTTP 200과 함께 인라인
  오류 + 재시도 안내, 500은 절대 아니다. 재시도 문구
  (templates/core/events/calendar.html): "잠시 후 다시 시도해 주세요.",
  복구 링크 문구 "다시 시도".
- 유효한 극단적 월(0001-01, 9999-12)은 오류 패널 없이 정상 렌더되고,
  데이터가 없으면 선택일 자체의 빈 상태 문구를 쓴다(서비스 설계 §9.4:
  "이 날짜에는 등록된 공식 이벤트가 없어요").
- 목록↔달력 전환 링크: 실제 템플릿으로 확인됨 —
  templates/core/events/list.html의 `<nav class="nav-links">`와
  templates/core/events/calendar.html의
  `<nav class="nav-links calendar-page-toggle">`, 둘 다 목록/달력 앵커
  쌍만 담고 쿼리스트링을 보존한다(`?{{ request.GET.urlencode }}`). 아래
  추출은 그 `<nav>` 블록으로 범위를 좁힌다 — 페이지는 사이트 전역 헤더 nav
  (templates/core/partials/_site_header.html)도 함께 렌더하는데, 그 안의
  단순 `href="/events/"` 링크가 범위 없는 검색에서 먼저 걸릴 수 있다.
- 월 이동(이전/다음) 링크: templates/core/events/calendar.html의
  `<nav class="calendar-month-nav">`로 확인됨. 페이지 상대 경로인
  `href="?month=...{{ extra_query }}"`로 렌더되므로(경로 접두 없음 — 브라우저는
  현재 페이지 기준으로 풀지만 Django 테스트 클라이언트는 절대 경로가
  필요해 아래 테스트가 따라갈 때 `/events/calendar/`를 앞에 붙인다).
  추출은 그 `<nav>`로 범위를 좁힌다 — 날짜 셀 그리드
  (templates/core/partials/_calendar_grid.html)도 보이는 모든 날짜(인접
  달의 채움 날짜 포함)마다 `href="?month=...&date=...#selected-date"`
  링크를 내므로, 범위 없는 검색은 의도한 이전/다음 컨트롤 대신 이걸 잡을
  수 있다. 필터 보존은 목적지 페이지 자체의 필터 체크박스 `checked`
  상태로 검증한다(기존 `filter-check` 마크업), `region="seoul"`은
  core.vocab.REGION의 실제 슬러그를 쓴다.
- 선택일의 행사는 제목으로 나타나고, 같은 표시 월 안의 다른 날 행사는
  나타나지 않는다(CAL-5-04/5-11). 단언은 `id="selected-date"` 이후의
  응답 본문으로 범위를 좁힌다(templates/core/events/calendar.html의
  `<section ... id="selected-date">`) — 월 그리드 자체도 각 날짜 셀에
  행사 제목을 그리므로(templates/core/partials/_calendar_grid.html의
  `.day-item`), 범위 없는 전체 본문 검색은 "다른 날" 행사의 제목도(그
  날짜의 그리드 셀 안에서) 찾아버려, 선택일 상세 목록에는 정확히 없는데도
  검사가 통과할 수 있다.
- CAL-5-09/5-10은 달력 전용 엔드포인트가 아니라 기존 EventInterest/
  UserEventStatus JSON API를 직접 호출한다 — 이 API들은 이 페이지보다
  먼저 있었으니 이미 초록일 수 있다. 새 동작을 검증하는 게 아니라 "달력
  빠른 작업은 새 엔드포인트 없이 기존 공개 계약을 재사용한다"는 전제를
  고정해 둔다.
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
    # `href="?{{ extra_query }}"`는 Django가 자동 이스케이프하는 변수
    # 치환이라, extra_query 값 안의 '&'는 응답 바이트에서 HTML 엔티티
    # '&amp;'로 렌더된다 — 실제 브라우저는 href를 URL로 쓰기 전에 이걸
    # '&'로 되돌리므로, 이 테스트도 "&amp;"가 섞인 문자열을 그대로
    # Client().get()에 넘기지 않도록 여기서 언이스케이프한다.
    return html.unescape(match.group(1))


def _extract_nav_hrefs(body, nav_class):
    """첫 <nav class="{nav_class}..."> 블록 안의 모든 href를 돌려준다 —
    페이지 전체가 아니라 특정 nav로 범위를 좁혀, 다른 곳의 무관한 링크
    (예: 전역 사이트 헤더의 /events/ 링크, 날짜 셀 그리드의 ?month=... 링크)를
    실수로 집어 오지 않는다. href는 HTML 언이스케이프한다(_extract_href
    주석 참고)."""
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
    """일부 nav 링크는 페이지 상대 쿼리 전용 href로 나온다(예:
    '?month=2026-08&region=seoul') — 브라우저는 현재 페이지 경로 기준으로
    풀지만, Django 테스트 클라이언트는 주어진 문자열을 그대로 경로로
    받아들이므로, href 자체에 경로가 없으면 현재 페이지 경로를 먼저
    붙인다."""
    if href.startswith("?"):
        return base_path + href
    return href


def _selected_date_section(body):
    """`id="selected-date"` 이후의 응답 본문을 돌려준다 — 월 그리드도 각
    날짜 셀에 행사 제목을 그리므로(모듈 독스트링 참고), CAL-5-04/5-11의
    제목 존재/부재 검사는 선택일 상세 섹션으로 범위를 좁힌다."""
    marker = 'id="selected-date"'
    index = body.find(marker)
    assert index != -1, f"{marker!r} 섹션을 찾을 수 없음"
    return body[index:]


# ---------------------------------------------------------------------------
# CAL-5-02 — 목록↔달력 전환은 필터 쿼리스트링을 보존한다
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_목록에서_달력으로_전환해도_지역_필터가_유지된다():
    list_resp = Client().get("/events/", {"region": "seoul"})
    assert list_resp.status_code == 200
    list_body = list_resp.content.decode()

    # 목록 페이지는 2026-07-22 에디토리얼 리빌드에서 전환 탭을 nav-links(알약)
    # 대신 events-tabs(밑줄 탭)로 바꿨다. 달력 페이지도 2026-07-23 에디토리얼
    # v2 리빌드에서 같은 events-tabs 셸을 공유하게 됐다.
    list_toggle_hrefs = _extract_nav_hrefs(list_body, "events-tabs")
    calendar_href = _first_containing(list_toggle_hrefs, "/events/calendar/")
    assert calendar_href is not None, "목록 페이지 events-tabs에 달력 전환 링크가 없음"
    assert "region=seoul" in calendar_href

    calendar_resp = Client().get(_as_absolute(calendar_href, base_path="/events/"))
    assert calendar_resp.status_code == 200
    calendar_body = calendar_resp.content.decode()

    calendar_toggle_hrefs = _extract_nav_hrefs(calendar_body, "events-tabs")
    list_href = _first_containing(calendar_toggle_hrefs, "/events/?")
    assert list_href is not None, "달력 페이지 events-tabs에 목록 전환 링크가 없음"
    assert "region=seoul" in list_href


# ---------------------------------------------------------------------------
# CAL-5-03 — 월 이동은 필터 쿼리스트링을 보존한다
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
# CAL-5-04 — 상세 목록에는 선택일의 행사만 표시된다
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
# CAL-5-05 — month이 없으면 오류 없이 오늘의 달로 기본 표시된다
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_month_파라미터가_없으면_오류_없이_당월이_표시된다(make_event):
    fixed_today = date(2026, 7, 19)
    make_event(title="당월기본표시행사", start_date=fixed_today, end_date=fixed_today)

    with patch("web.views.events.timezone.localdate", return_value=fixed_today):
        resp = Client().get("/events/calendar/")

    assert resp.status_code == 200
    body = resp.content.decode()
    assert "요청한 날짜를 확인할 수 없어요" not in body
    assert "당월기본표시행사" in body


# ---------------------------------------------------------------------------
# CAL-5-06 — 무효한 month/date → 200 + 인라인 오류 패널 + 복구 링크
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
# CAL-5-07 — 유효한 극단적 월은 클램프 없이 그대로 렌더된다
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
    assert "이 날짜에는 등록된 공식 이벤트가 없어요" in body


# ---------------------------------------------------------------------------
# CAL-5-08 — 월 조회 실패는 500이 아니라 오류 패널로 처리된다
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_월_조회가_실패하면_500대신_오류_패널과_재시도_안내가_표시된다(monkeypatch):
    def _raise(*args, **kwargs):
        raise RuntimeError("월 조회 실패 주입")

    monkeypatch.setattr("web.views.events.list_published_events_for_month", _raise)

    resp = Client().get("/events/calendar/")

    assert resp.status_code == 200
    assert "다시 시도" in resp.content.decode()


# ---------------------------------------------------------------------------
# CAL-5-09/5-10 — 달력 빠른 작업은 기존 공개 API 계약을 그대로 재사용한다
# (전제 재확인용 — 이미 초록일 수 있음, 모듈 독스트링 참고).
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
# CAL-5-11 — 여러 날 진행되는 행사는 시작일뿐 아니라 기간 중 어느 날을
# 선택해도 상세 목록에 나타난다
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
# CALFIX-1 — active_filter_count가 컨텍스트에 노출된다(달력 검토 수정 계획
# .docs/plans/2026-07-19-calendar-review-fixes-plan.md 단계 1)
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
# CAL-EDIT-1 — active_filter_chips가 컨텍스트에 노출되며, event_list와 같은
# 방식으로 파생된다(편집 계획 §D)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_필터가_적용된_달력_요청의_컨텍스트에_적용_필터_칩이_담긴다():
    resp = Client().get("/events/calendar/", {"region": "seoul", "q": "포스터"})

    assert resp.status_code == 200
    chips = resp.context["active_filter_chips"]
    assert "검색: 포스터" in chips
    assert any("서울" in chip for chip in chips)


# ---------------------------------------------------------------------------
# CAL-EDIT-2 — weeks[].items[]가 날짜 셀 카테고리 바/점 표시를 위한
# category_slug를 담는다(편집 계획 §D)
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
