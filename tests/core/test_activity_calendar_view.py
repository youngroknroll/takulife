"""활동 달력 SSR 뷰(이중 달력 테스트 목록 §단계 5, Activity 분) — CAL-5-01과
새로 발견된 CAL-5-12~16 시나리오(.docs/plans/2026-07-19-dual-calendar-test-list.md에
기록).

웹 계층 계약:
- `GET /archive/calendar/`, name="archive-calendar-page", `@login_required`
  (core/views.py의 다른 `archive/*` 뷰와 동일한 규약).
- 쿼리 파라미터 `month=YYYY-MM`/`date=YYYY-MM-DD`는 Events 달력과 같은 파싱
  규칙을 쓴다(서비스 설계 §11.1: 파라미터 부재와 "빈 값이지만 존재"를
  구분, 무효값 → `calendar_error="invalid"`). `type=`은 반복 파라미터로
  5개 그룹(schedule/interest/status/visit/goods) 중 일부를 고르며, 각각
  archive.activity_calendar_queries의 kind 상수로 매핑된다(schedule→SCHEDULE_KIND,
  interest→INTEREST_ADDED/REMOVED + §7.5 레거시 찜 폴백,
  status→STATUS_CHANGED/REMOVED, visit→VISIT_KIND + VISIT_RECORD_CREATED,
  goods→GOODS_ACQUIRED_KIND + COLLECTION_ITEM_CREATED/ORGANIZED).
- 선택일 상세 섹션은 `id="selected-date"`(Events calendar.html과 같은
  규약)이며 아래 `_selected_date_section`으로 잘라낸다 — 월 그리드도 각
  날짜 셀에 항목 라벨을 그리므로(달력 셀 제목 충돌 교훈이 여기도 그대로
  적용된다), 모든 존재/부재 검사는 본문 전체가 아니라 이 섹션으로 범위를
  좁힌다.
- 월 이동 링크는 `<nav class="calendar-month-nav">`(Events calendar.html과
  같은 클래스)이며, Events가 `extra_query`로 region/category/status/q를
  보존하듯 `type=`을 보존한다.
- 표시 월 전체에 활동이 0건이면 이 저장소에서 이미 쓰는 이중 CTA 빈 상태
  패턴을 그대로 재사용한다(templates/core/partials/_home_collection_snapshot.html의
  `<div class="empty-actions"><a href="/events/">행사 찾기</a>
  <a href="/collection/new/">굿즈 등록</a></div>`, 서비스 설계 §9.4) — 링크
  문구는 아직 확정 전이라 href 두 개만 검증하고 문구는 검증하지 않는다.
- 무효한 month 오류 패널은 Events 달력과 동일한 문구다(프런트 사전검토
  §A-13) — "요청한 날짜를 확인할 수 없어요" 제목, "이번 달 보기" 복구 링크.
"""
import html
import re
from datetime import date
from urllib.parse import parse_qs, urlparse

import pytest
from django.test import Client
from django.utils import timezone

from archive.models import ActivityLogEntry, CollectionItem, UserEventStatus, VisitRecord

pytestmark = pytest.mark.web


def _extract_href(body, link_text):
    match = re.search(
        rf'<a[^>]*href="([^"]*)"[^>]*>\s*{re.escape(link_text)}\s*</a>', body
    )
    assert match, f"{link_text!r} 링크를 찾을 수 없음"
    return html.unescape(match.group(1))


def _extract_block(body, *, tag, class_prefix):
    """<{tag} class="{class_prefix}...">...</{tag}> 블록의 내부 HTML을
    돌려준다 — 페이지 전체가 아니라 특정 컨테이너로 범위를 좁힌다. 범위를
    좁히지 않으면 전역 사이트 헤더의 /events/ 링크처럼 무관한 링크까지
    걸릴 수 있다."""
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


def _find_cell(weeks, target_date):
    for week in weeks:
        for cell in week:
            if cell["date"] == target_date:
                return cell
    raise AssertionError(f"{target_date} 셀을 weeks에서 찾을 수 없음")


def _selected_date_section(body):
    """`id="selected-date"` 이후의 응답 본문을 돌려준다 — 월 그리드도 각
    날짜 셀에 항목 라벨을 그리므로, 존재/부재 검사는 선택일 상세 섹션으로
    범위를 좁혀야 한다(모듈 독스트링 참고)."""
    marker = 'id="selected-date"'
    index = body.find(marker)
    assert index != -1, f"{marker!r} 섹션을 찾을 수 없음"
    return body[index:]


# ---------------------------------------------------------------------------
# CAL-5-01 — 비로그인 접근은 요청 URL 전체(쿼리스트링 포함)를 next=에 담아
# 로그인으로 리다이렉트한다
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
# CAL-5-12 — 로그인한 본인의 활동만 렌더되고, 다른 사용자의 활동은 절대
# 렌더되지 않는다
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
    # 프라이버시 유출 검사는 상세 섹션이 아니라 본문 전체를 본다 — 다른
    # 사용자의 활동은 선택일 목록에서만 빠지는 게 아니라 페이지 어디에도
    # 나타나면 안 된다.
    assert "타인전용달력방문행사" not in body
    assert "본인전용달력방문행사" in _selected_date_section(body)


# ---------------------------------------------------------------------------
# CAL-5-13 — type= 필터가 렌더 범위를 좁히고, 월 이동에도 그대로 보존된다
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
# CAL-5-14 — 활동이 0건인 달은 이중 CTA 빈 상태를 렌더한다
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
# CAL-5-15 — 무효한 month → 200과 함께 인라인 오류 패널 + 복구 링크
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
# CAL-5-16 — 선택일 상세 목록에는 그 날짜의 항목만 담긴다: 실제 방문
# (visited_on 일치)과 기간이 그 날짜를 포함하는 예정 행사는 포함하고, 다른
# 날짜의 항목은 제외한다
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


# ---------------------------------------------------------------------------
# D8(활동 달력 에디토리얼 계획 §8-A) — 필터 접이식 패널이 사라져서 그
# "N개 선택됨" 표시에 쓰던 active_filter_count는 이제 이 뷰에 없는
# 컨텍스트다. 반대를 검증하던 이전 CALFIX-2 테스트를 대체한다.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_활동_달력_컨텍스트에는_더이상_active_filter_count가_없다(user_client):
    _, client = user_client()

    resp = client.get("/archive/calendar/", {"type": ["visit", "goods"]})

    assert resp.status_code == 200
    assert "active_filter_count" not in resp.context


# ---------------------------------------------------------------------------
# B1 — 하루 셀에는 항목 요약을 최대 2개까지만 노출하고 나머지는 초과분
# 카운트로 담는다(활동 달력 에디토리얼 계획 §4-a B1)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_같은_날_아이템이_3건이면_셀에는_2건만_담기고_초과분이_more_count에_담긴다(
    user_client,
):
    user, client = user_client()
    for name in ("셀아이템첫번째굿즈", "셀아이템두번째굿즈", "셀아이템세번째굿즈"):
        CollectionItem.objects.create(user=user, name=name, acquired_on=date(2026, 7, 10))

    resp = client.get("/archive/calendar/", {"month": "2026-07", "date": "2026-07-10"})

    assert resp.status_code == 200
    cell = _find_cell(resp.context["weeks"], date(2026, 7, 10))
    assert cell["count"] == 3
    assert len(cell["items"]) == 2
    assert all(entry["group"] == "goods" for entry in cell["items"])
    assert cell["more_count"] == 1


# ---------------------------------------------------------------------------
# B2 — "status" 활동만 있는 날은 어디서나 빈 것으로 집계/표시된다
# (셀 count, items, aria-label이 쓰는 수, 선택일 목록이 전부 0/빈 리스트로
# 일치해야 한다 — PO 결정 2 / BIR Medium)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_상태_변경만_있는_날은_셀_카운트와_아이템과_선택일_목록이_모두_0이다(
    user_client,
):
    user, client = user_client()
    ActivityLogEntry.objects.create(
        user=user,
        kind=ActivityLogEntry.Kind.STATUS_CHANGED,
        occurred_at=timezone.make_aware(timezone.datetime(2026, 7, 10, 10, 0)),
        subject_label="상태변경만있는날행사",
    )

    resp = client.get("/archive/calendar/", {"month": "2026-07", "date": "2026-07-10"})

    assert resp.status_code == 200
    cell = _find_cell(resp.context["weeks"], date(2026, 7, 10))
    assert cell["count"] == 0
    assert cell["items"] == []
    assert cell["more_count"] == 0
    assert resp.context["selected_items"] == []
    assert "상태변경만있는날행사" not in _selected_date_section(resp.content.decode())


# ---------------------------------------------------------------------------
# B5 — ?type=status는 여전히 파싱 가능해야 하고(하위 호환 북마크), B2와
# 결합해도 진짜 0건인 날을 크래시나 거짓 카운트 없이 그대로 렌더해야 한다
# (BIR Medium이 같은 수정으로 묶은 항목)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_type가_status인_북마크는_500이나_거짓_카운트_없이_0건으로_렌더된다(
    user_client,
):
    user, client = user_client()
    ActivityLogEntry.objects.create(
        user=user,
        kind=ActivityLogEntry.Kind.STATUS_CHANGED,
        occurred_at=timezone.make_aware(timezone.datetime(2026, 7, 10, 10, 0)),
        subject_label="type_status_북마크확인행사",
    )

    resp = client.get(
        "/archive/calendar/", {"month": "2026-07", "date": "2026-07-10", "type": "status"}
    )

    assert resp.status_code == 200
    cell = _find_cell(resp.context["weeks"], date(2026, 7, 10))
    assert cell["count"] == 0


# ---------------------------------------------------------------------------
# B3 — 범례 카운트는 표시 월의 종류별 건수를 반영한다(4개 그룹만 — "status"
# 키는 없음). 뷰가 이미 가져온 항목을 그대로 재사용한다
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_범례_카운트가_표시_월의_종류별_건수_4종을_반영한다(
    user_client, make_event
):
    user, client = user_client()
    scheduled_event = make_event(
        title="범례카운트일정행사", start_date=date(2026, 7, 3), end_date=date(2026, 7, 5)
    )
    UserEventStatus.objects.create(
        user=user, event=scheduled_event, status=UserEventStatus.Status.PLANNED
    )
    for i in range(2):
        ActivityLogEntry.objects.create(
            user=user,
            kind=ActivityLogEntry.Kind.INTEREST_ADDED,
            occurred_at=timezone.make_aware(timezone.datetime(2026, 7, 10, 10, i)),
            subject_label=f"범례카운트찜{i}",
        )
    for i in range(3):
        CollectionItem.objects.create(
            user=user, name=f"범례카운트굿즈{i}", acquired_on=date(2026, 7, 12)
        )

    resp = client.get("/archive/calendar/", {"month": "2026-07"})

    assert resp.status_code == 200
    assert resp.context["kind_counts"] == {
        "schedule": 1,
        "interest": 2,
        "visit": 0,
        "goods": 3,
    }


# ---------------------------------------------------------------------------
# B4 — 머스트헤드 통계(status_counts)는 기존 user_status_counts 헬퍼가 주는
# 전체 기간 합계이며 표시 월과 무관하다 — kind_counts와는 다른 컨텍스트
# 키에 담긴다(WED 구속 기준)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_머스트헤드_통계는_표시_월과_무관하게_전체_기간_상태_카운트를_반영한다(
    user_client, make_event
):
    user, client = user_client()
    # 그냥 다른 달이 아니라 일부러 미래 달로 잡는다: user_status_counts
    # (archive/queries.py)는 파생 상태(자동 놓침 반영)를 센다 — 행사 기간이
    # 이미 끝난 PLANNED 상태는 "planned"가 아니라 "missed"로 파생된다(해당
    # 함수 독스트링 참고). 과거의 다른 달로 잡으면 이 픽스처의 상태 자체가
    # 아래 단언 밑에서 조용히 뒤바뀌므로, 테스트 스위트가 실행되는 "오늘"이
    # 언제든 미래에 있어야 "planned"를 계속 검증하면서 동시에 카운트가
    # 표시 월 밖의 달까지 걸친다는 것도 증명할 수 있다.
    other_month_event = make_event(
        title="통계전체기간확인행사", start_date=date(2026, 12, 1), end_date=date(2026, 12, 1)
    )
    UserEventStatus.objects.create(
        user=user, event=other_month_event, status=UserEventStatus.Status.PLANNED
    )

    resp = client.get("/archive/calendar/", {"month": "2026-07"})

    assert resp.status_code == 200
    # archive.queries.user_status_counts를 호출하지 않고 리터럴 값으로
    # 기대한다: 사용자에게 상태 행이 정확히 1건이므로 이것이 파생 상태의
    # 전체 내역이다 — 헬퍼와 뷰가 같은 방식으로 둘 다 틀려도 통과해버리는
    # 배선 확인이 아니다. 카운트가 표시 월(7월) 밖의 달(12월)까지 걸친다는
    # 것도 함께 증명한다.
    assert resp.context["status_counts"] == {"planned": 1, "visited": 0, "missed": 0}
    assert resp.context["status_counts"] is not resp.context["kind_counts"]


# ---------------------------------------------------------------------------
# B6 — 날짜 점프 검색(신규 계약, §4-a-1). GET ?q=...는 일치하는 활동의
# 날짜로 PRG 리다이렉트한다. 일치가 없으면 오늘로 되돌아가지 않고 현재
# 표시 월을 유지하며 q를 보존한다.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_검색어가_일치하면_해당_날짜로_PRG_리다이렉트된다(user_client):
    user, client = user_client()
    CollectionItem.objects.create(
        user=user, name="검색점프뷰단일일치굿즈", acquired_on=date(2026, 7, 10)
    )

    resp = client.get("/archive/calendar/", {"q": "검색점프뷰단일일치"})

    assert resp.status_code == 302
    parsed = urlparse(resp.url)
    query = parse_qs(parsed.query)
    assert query["month"] == ["2026-07"]
    assert query["date"] == ["2026-07-10"]
    assert parsed.fragment == "selected-date"


@pytest.mark.django_db
def test_검색어가_여러_건_일치하면_가장_최근_날짜로_리다이렉트된다(user_client):
    user, client = user_client()
    CollectionItem.objects.create(
        user=user, name="검색점프뷰다중일치굿즈오래됨", acquired_on=date(2026, 1, 5)
    )
    CollectionItem.objects.create(
        user=user, name="검색점프뷰다중일치굿즈최근", acquired_on=date(2026, 7, 20)
    )

    resp = client.get("/archive/calendar/", {"q": "검색점프뷰다중일치"})

    assert resp.status_code == 302
    query = parse_qs(urlparse(resp.url).query)
    assert query["month"] == ["2026-07"]
    assert query["date"] == ["2026-07-20"]


@pytest.mark.django_db
def test_검색어가_무일치면_리다이렉트하지_않고_현재_월을_유지하며_검색어를_보존한다(
    user_client,
):
    _, client = user_client()

    resp = client.get(
        "/archive/calendar/", {"month": "2026-03", "date": "2026-03-15", "q": "존재하지않는검색어"}
    )

    assert resp.status_code == 200
    assert resp.context["month_label"] == "2026년 3월"
    assert resp.context["q"] == "존재하지않는검색어"
    assert resp.context["search_no_match"] is True


@pytest.mark.django_db
def test_검색어가_빈_문자열이면_검색을_시도하지_않고_평소대로_렌더된다(user_client):
    _, client = user_client()

    resp = client.get("/archive/calendar/", {"month": "2026-07", "q": ""})

    assert resp.status_code == 200
    assert resp.context["q"] == ""
    assert resp.context["search_no_match"] is False


@pytest.mark.django_db
def test_다른_사용자의_활동은_검색으로_찾아지지_않는다(user_client, make_user):
    user, client = user_client()
    other_user = make_user(username="search-jump-view-other-user")
    CollectionItem.objects.create(
        user=other_user, name="타인검색점프뷰굿즈", acquired_on=date(2026, 7, 10)
    )

    resp = client.get(
        "/archive/calendar/", {"month": "2026-07", "date": "2026-07-01", "q": "타인검색점프뷰"}
    )

    assert resp.status_code == 200
    assert resp.context["search_no_match"] is True


@pytest.mark.django_db
def test_활성_종류_필터가_검색에도_적용되어_필터_밖_일치는_건너뛴다(
    user_client, make_event
):
    user, client = user_client()
    scheduled_event = make_event(
        title="검색필터병용일치행사", start_date=date(2026, 7, 3), end_date=date(2026, 7, 3)
    )
    UserEventStatus.objects.create(
        user=user, event=scheduled_event, status=UserEventStatus.Status.PLANNED
    )
    CollectionItem.objects.create(
        user=user, name="검색필터병용일치굿즈", acquired_on=date(2026, 7, 20)
    )

    resp = client.get(
        "/archive/calendar/", {"q": "검색필터병용일치", "type": "schedule"}
    )

    assert resp.status_code == 302
    query = parse_qs(urlparse(resp.url).query)
    assert query["date"] == ["2026-07-03"]
    assert query["type"] == ["schedule"]


# ---------------------------------------------------------------------------
# D1(활동 달력 에디토리얼 계획 §8-A) — kind_counts는 활성 ?type= 필터와
# 무관하게 보이는 4개 그룹 전체의 표시 월 합계를 유지한다 — 그래야 종류를
# 다시 켰을 때 항상 정확한 카운트가 보인다(WED/BIR 독립 합의: 필터셋에서
# 파생하면 방금 끈 종류가 0으로 보임).
# ---------------------------------------------------------------------------


def _find_kind_filter(kind_filters, group):
    for entry in kind_filters:
        if entry["group"] == group:
            return entry
    raise AssertionError(f"{group!r} kind_filters 항목을 찾을 수 없음")


@pytest.mark.django_db
def test_type_필터가_있어도_kind_counts는_필터와_무관하게_표시_월_전체_건수를_유지한다(
    user_client, make_event
):
    user, client = user_client()
    scheduled_event = make_event(
        title="필터무관카운트일정행사", start_date=date(2026, 7, 3), end_date=date(2026, 7, 3)
    )
    UserEventStatus.objects.create(
        user=user, event=scheduled_event, status=UserEventStatus.Status.PLANNED
    )
    for i in range(2):
        ActivityLogEntry.objects.create(
            user=user,
            kind=ActivityLogEntry.Kind.INTEREST_ADDED,
            occurred_at=timezone.make_aware(timezone.datetime(2026, 7, 10, 10, i)),
            subject_label=f"필터무관카운트찜{i}",
        )
    for i in range(3):
        CollectionItem.objects.create(
            user=user, name=f"필터무관카운트굿즈{i}", acquired_on=date(2026, 7, 12)
        )

    filtered_resp = client.get(
        "/archive/calendar/", {"month": "2026-07", "type": "visit"}
    )
    unfiltered_resp = client.get("/archive/calendar/", {"month": "2026-07"})

    assert filtered_resp.status_code == 200
    assert unfiltered_resp.status_code == 200
    expected = {"schedule": 1, "interest": 2, "visit": 0, "goods": 3}
    assert filtered_resp.context["kind_counts"] == expected
    assert unfiltered_resp.context["kind_counts"] == expected


# ---------------------------------------------------------------------------
# D2/D3(활동 달력 에디토리얼 계획 §8-A) — 범례는 클릭 가능한 다중 토글
# 필터다: 각 종류의 링크는 비활성일 때 자신을 추가하고 활성일 때 자신을
# 제거하며, 별도의 리셋 링크는 month/date는 유지한 채 모든 type=을 지운다
# (§9-1의 hidden-input 교훈과 같은 이유).
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_비활성_종류의_토글_url은_그_종류를_추가한다(user_client):
    _, client = user_client()

    resp = client.get(
        "/archive/calendar/", {"month": "2026-07", "date": "2026-07-10", "type": "schedule"}
    )

    assert resp.status_code == 200
    goods_filter = _find_kind_filter(resp.context["kind_filters"], "goods")
    assert goods_filter["is_active"] is False
    toggle_query = parse_qs(urlparse(goods_filter["toggle_url"]).query)
    assert toggle_query["type"] == ["schedule", "goods"]


@pytest.mark.django_db
def test_활성_종류의_토글_url은_그_종류를_제거한다(user_client):
    _, client = user_client()

    resp = client.get(
        "/archive/calendar/",
        {"month": "2026-07", "date": "2026-07-10", "type": ["schedule", "goods"]},
    )

    assert resp.status_code == 200
    schedule_filter = _find_kind_filter(resp.context["kind_filters"], "schedule")
    assert schedule_filter["is_active"] is True
    toggle_query = parse_qs(urlparse(schedule_filter["toggle_url"]).query)
    assert toggle_query["type"] == ["goods"]


@pytest.mark.django_db
def test_토글_url에_현재_month와_date가_보존된다(user_client):
    _, client = user_client()

    resp = client.get(
        "/archive/calendar/", {"month": "2026-07", "date": "2026-07-10", "type": "visit"}
    )

    assert resp.status_code == 200
    interest_filter = _find_kind_filter(resp.context["kind_filters"], "interest")
    toggle_query = parse_qs(urlparse(interest_filter["toggle_url"]).query)
    assert toggle_query["month"] == ["2026-07"]
    assert toggle_query["date"] == ["2026-07-10"]


@pytest.mark.django_db
def test_전체_보기_리셋_url에는_type이_없고_month와_date가_보존된다(user_client):
    _, client = user_client()

    resp = client.get(
        "/archive/calendar/",
        {"month": "2026-07", "date": "2026-07-10", "type": ["schedule", "goods"]},
    )

    assert resp.status_code == 200
    reset_query = parse_qs(urlparse(resp.context["reset_filter_url"]).query)
    assert "type" not in reset_query
    assert reset_query["month"] == ["2026-07"]
    assert reset_query["date"] == ["2026-07-10"]


@pytest.mark.django_db
def test_활성_플래그가_selected_types를_반영한다(user_client):
    _, client = user_client()

    resp = client.get(
        "/archive/calendar/", {"type": ["interest", "visit"]}
    )

    assert resp.status_code == 200
    kind_filters = resp.context["kind_filters"]
    active_groups = {entry["group"] for entry in kind_filters if entry["is_active"]}
    assert active_groups == {"interest", "visit"}


# ---------------------------------------------------------------------------
# 활동 달력 백로그 #1 — has_any_items는 status 제외를 반영해야 한다: 표시
# 월에 "status" 그룹 활동만 있고 화면에 그려지는 활동은 없으면, 빈 상태
# CTA(has_any_items=False)가 떠야 한다. status는 §4-a B1/B2에서 그리드/상세
# 어디에도 표시되지 않으므로 has_any_items도 같은 규칙을 따라야 한다.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_status_활동만_있는_달은_활동이_없는_것으로_취급되어_빈_상태_CTA를_렌더한다(
    user_client,
):
    user, client = user_client()
    ActivityLogEntry.objects.create(
        user=user,
        kind=ActivityLogEntry.Kind.STATUS_REMOVED,
        occurred_at=timezone.make_aware(timezone.datetime(2026, 7, 10, 9, 0)),
        subject_label="상태전용달력행사",
    )

    resp = client.get("/archive/calendar/", {"month": "2026-07", "date": "2026-07-10"})

    assert resp.status_code == 200
    assert resp.context["has_any_items"] is False
    body = resp.content.decode()
    detail_section = _selected_date_section(body)
    assert "아직 기록이 없어요" in detail_section
    assert "상태전용달력행사" not in body


@pytest.mark.django_db
def test_표시_가능한_활동이_있으면_같은_달의_status_활동과_무관하게_has_any_items가_참이다(
    user_client, make_event
):
    user, client = user_client()
    visited_event = make_event(title="정상활동있음달력행사")
    VisitRecord.objects.create(user=user, event=visited_event, visited_on=date(2026, 7, 10))
    ActivityLogEntry.objects.create(
        user=user,
        kind=ActivityLogEntry.Kind.STATUS_CHANGED,
        occurred_at=timezone.make_aware(timezone.datetime(2026, 7, 15, 9, 0)),
        subject_label="같은달상태전용행사",
    )

    resp = client.get("/archive/calendar/", {"month": "2026-07", "date": "2026-07-10"})

    assert resp.status_code == 200
    assert resp.context["has_any_items"] is True


@pytest.mark.django_db
def test_필터로_모두_걸러진_달은_has_any_items가_거짓이다(user_client, make_event):
    user, client = user_client()
    visited_event = make_event(title="필터로걸러진달력행사")
    VisitRecord.objects.create(user=user, event=visited_event, visited_on=date(2026, 7, 10))

    resp = client.get(
        "/archive/calendar/", {"month": "2026-07", "date": "2026-07-10", "type": "goods"}
    )

    assert resp.status_code == 200
    assert resp.context["has_any_items"] is False


# ---------------------------------------------------------------------------
# CAL-DEFECT-01 (2026-07-31 중복 표시 결함 계획 §7) — 방문 기록 1건은 방문
# 활동 1건으로만 집계돼야 한다. POST /api/visit-records/는 내부적으로
# complete_visit_with_record를 호출해 VisitRecord(상태 테이블)와
# ActivityLogEntry(행동 로그)를 함께 쓰므로, 현재 뷰가 두 출처를 같은
# "visit" 그룹으로 묶으면 이 한 번의 요청만으로도 중복이 재현된다.
# (아키텍처 가드 tests/core/test_architecture_boundaries.py가 client 계열
# 픽스처를 쓰는 view 테스트 파일의 서비스·쿼리 계층 임포트를 금지하므로,
# 준비는 서비스 함수 직접 호출이 아니라 실제 API 엔드포인트를 경유한다.)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_방문_기록을_하나_남기면_달력에서_방문_활동이_한_건으로만_집계된다(
    user_client, make_event
):
    _, client = user_client()
    event = make_event(title="방문중복집계확인행사")
    today = timezone.localdate()
    # visited_on을 오늘로 맞춰야 ActivityLogEntry.occurred_at(기본값 now())의
    # 로컬 날짜와 같은 달력 셀에 떨어져 결함이 재현된다.
    create_resp = client.post(
        "/api/visit-records/",
        {"event": event.id, "visited_on": today.isoformat()},
        content_type="application/json",
    )
    assert create_resp.status_code == 201

    resp = client.get("/archive/calendar/")

    assert resp.status_code == 200
    cell = _find_cell(resp.context["weeks"], today)
    assert cell["count"] == 1
    assert resp.context["kind_counts"]["visit"] == 1


# ---------------------------------------------------------------------------
# CAL-DEFECT-02 / CAL-DEFECT-03 (2026-07-31 중복 표시 결함 계획 §7) — 굿즈
# 등록 1건도 방문과 같은 이유로 상태 테이블(CollectionItem)과 행동 로그
# (ActivityLogEntry)에 동시에 흔적을 남긴다. 두 시나리오는 "goods" 그룹에서
# COLLECTION_ITEM_CREATED를 빼는 같은 수정 하나로 함께 닫히므로, 02를 먼저
# Green으로 만들지 않고 03과 함께 Red로 세운다 — 순서를 바꾸면 03이 프로덕션
# 변경 없이 우연히 통과해 버려 실패했어야 할 이유를 확인할 기회가 사라진다.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_굿즈를_하나_등록하면_달력에서_굿즈_활동이_한_건으로만_집계된다(user_client):
    _, client = user_client()
    today = timezone.localdate()
    # acquired_on을 오늘로 맞춰야 ActivityLogEntry.occurred_at(기본값 now())의
    # 로컬 날짜와 같은 달력 셀에 떨어져 결함이 재현된다.
    create_resp = client.post(
        "/api/collection-items/",
        {"name": "굿즈중복집계확인아이템", "acquired_on": today.isoformat()},
        content_type="application/json",
    )
    assert create_resp.status_code == 201

    resp = client.get("/archive/calendar/")

    assert resp.status_code == 200
    cell = _find_cell(resp.context["weeks"], today)
    assert cell["count"] == 1
    assert resp.context["kind_counts"]["goods"] == 1


@pytest.mark.django_db
def test_굿즈를_하드_삭제하면_등록_로그가_남아도_달력에_표시되지_않는다(user_client):
    _, client = user_client()
    today = timezone.localdate()
    create_resp = client.post(
        "/api/collection-items/",
        {"name": "굿즈하드삭제잔존확인아이템", "acquired_on": today.isoformat()},
        content_type="application/json",
    )
    assert create_resp.status_code == 201
    item_id = create_resp.json()["id"]
    # DELETE /api/collection-items/<id>/는 CollectionItemDetailView의 기본
    # destroy 경로(하드 삭제)를 그대로 탄다 — ActivityLogEntry는
    # on_delete=SET_NULL이라 subject_label 스냅샷을 지닌 채 살아남는데, 이
    # 잔존 로그가 유령 표시의 메커니즘이다.
    delete_resp = client.delete(f"/api/collection-items/{item_id}/")
    assert delete_resp.status_code == 204

    resp = client.get("/archive/calendar/")

    assert resp.status_code == 200
    cell = _find_cell(resp.context["weeks"], today)
    assert cell["count"] == 0
    assert resp.context["kind_counts"]["goods"] == 0
    # 오늘 하루 동안 다른 활동은 전혀 만들지 않았으므로, 선택일 목록이 완전히
    # 비어 있는지 확인하는 것만으로 "그 굿즈가 안 보인다"는 사실이 충분히
    # 증명된다 — 다른 그룹 항목이 섞여 들어와 이름 검사만으로는 놓칠 수 있는
    # 여지 자체가 없다.
    assert resp.context["selected_items"] == []


# ---------------------------------------------------------------------------
# CAL-DEFECT-04 (2026-07-31 중복 표시 결함 계획 §7) — 굿즈 수량만 고치는
# 것은 "언제 획득했나"를 바꾸지 않으므로 달력에 새 활동이 생기면 안 된다
# (사용자 결정: 굿즈 수정은 달력에 표시하지 않는다). visit/goods 생성
# 시점과 달리 이건 별개 kind(COLLECTION_ITEM_ORGANIZED)라 독자적인 Red가
# 필요하다.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_굿즈_수량만_수정하면_달력에_새_활동이_생기지_않는다(user_client):
    _, client = user_client()
    today = timezone.localdate()
    # 정리(organize) 로그의 occurred_at은 서비스가 실제 현재 시각(오늘)으로
    # 찍으므로, 획득일을 오늘과 겹치게 두면 두 활동이 같은 셀에 섞여 "새
    # 활동이 생겼는지"를 구분할 수 없다. 이번 달 안에서 오늘과 다른 날짜가
    # 필요한데, 오늘이 매월 1일이면 "이번 달 1일"을 못 쓰므로 그때만 2일을
    # 쓴다 — 어느 달이든 1일과 2일은 항상 존재해 월초에도 안전하다.
    acquired_on = today.replace(day=2) if today.day == 1 else today.replace(day=1)
    create_resp = client.post(
        "/api/collection-items/",
        {
            "name": "굿즈수정활동미생성확인아이템",
            "acquired_on": acquired_on.isoformat(),
            "quantity": 1,
        },
        content_type="application/json",
    )
    assert create_resp.status_code == 201
    item_id = create_resp.json()["id"]
    update_resp = client.patch(
        f"/api/collection-items/{item_id}/",
        {"quantity": 5},
        content_type="application/json",
    )
    assert update_resp.status_code == 200

    resp = client.get("/archive/calendar/")

    assert resp.status_code == 200
    today_cell = _find_cell(resp.context["weeks"], today)
    assert today_cell["count"] == 0
    assert resp.context["kind_counts"]["goods"] == 1
    acquired_cell = _find_cell(resp.context["weeks"], acquired_on)
    assert acquired_cell["count"] == 1
