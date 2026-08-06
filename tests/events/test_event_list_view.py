"""공개 목록 화면 뷰(web.views.event_list)를 검증한다.

검증 대상 동작: 유효하지 않거나 일치하지 않는 필터 값은 빈 상태
("행사 없음")로 렌더링되며, 오류 화면으로 이어지지 않는다. JSON API는
같은 입력을 여전히 400으로 거부한다(test_events_api.py에서 다룬다) —
목록 화면만 우아하게 대응한다.
"""
import re
from datetime import timedelta
from html import unescape
from urllib.parse import parse_qs, quote, urlparse

import pytest
from django.test import Client
from django.utils import timezone

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

    def test_사이드바_폼의_빈_상태_값은_오류_없이_다른_필터와_함께_정상_동작한다(self, make_event):
        """사이드바 폼은 항상 status=""(전체)와 sort=""를 제출한다; 빈
        status가 ValidationError나 빈 상태로 이어지면 안 되고, 다른 필터(여기선
        region)와도 여전히 함께 동작해야 한다.

        web/views/events.py::event_list는 비어있는 status를 "active"로 기본
        처리한다 — 빈 status가 더는 "필터 없음"을 뜻하지 않는다는 계약은
        아래 test_사이드바_폼의_빈_상태_값도_기본적으로_진행_예정만_남긴다가 검증한다.
        이 테스트는 "빈 값이 오류를 내지 않는다"는 부분만 지킨다."""
        make_event(title="Seoul match", region="seoul")

        resp = Client().get(
            "/events/", {"region": "seoul", "status": "", "sort": ""}
        )

        assert resp.status_code == 200
        body = resp.content.decode()
        assert "검색 결과" in body
        assert "Seoul match" in body

    def test_사이드바_폼의_빈_상태_값도_기본적으로_진행_예정만_남긴다(self, make_event):
        """현재 계약: 명시적으로 빈 status=""는 status 파라미터가 없는 것과
        동일하게 취급돼 "active"로 기본 처리되고 종료된 행사는 제외된다 —
        검증용 픽스처는 실제 과거 end_date를 가져야 한다. end_date가 NULL인
        행사는 기본값과 무관하게 살아남으므로 이 값이 아니면 아무것도
        증명하지 못한다."""
        today = timezone.localdate()
        make_event(
            title="Seoul closed",
            region="seoul",
            start_date=today - timedelta(days=32),
            end_date=today - timedelta(days=1),
        )

        resp = Client().get(
            "/events/", {"region": "seoul", "status": "", "sort": ""}
        )

        assert resp.status_code == 200
        assert "Seoul closed" not in resp.content.decode()


@pytest.mark.django_db
class TestEventListAuthenticatedRows:
    """로그인한 사용자 본인의 상태/찜 여부가 목록 카드에 반영된다
    (web.views.events._attach_display의 인증 분기)."""

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
    """각 행은 카드의 장소 표시줄용 한글 region_label을 담는다
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

    def test_상태를_전체로_필터링하면_활성_필터_칩에_전체가_표시된다(self, make_event):
        """status='all'이 그대로 'all' 칩으로 새어나가면 안 된다
        (EVENT_STATUS_LABELS에는 'all' 항목이 없다 — 사이드바의 "전체" 오버라이드일
        뿐 EVENT_STATUS의 일원은 아니다. 달력의 전용 value="" 전체상태 라디오와
        같은 이유로 그냥 추가할 수 없다)."""
        make_event(title="전체상태칩행사")

        resp = Client().get("/events/", {"status": "all"})

        assert resp.status_code == 200
        assert "전체" in resp.context["active_filter_chips"]
        assert "all" not in resp.context["active_filter_chips"]


@pytest.mark.django_db
class TestEventListPagerQEncoding:
    """페이저의 ?q= 링크는 검색어를 URL 인코딩해야 한다. 그러지 않으면 '#'이
    들어간 값이 클릭 시 URL 프래그먼트로 잘려 나머지 쿼리스트링을 잃는다.

    /events/의 페이지네이션은 공용 페이저 파셜(templates/core/partials/_pager.html)이
    렌더링하며, 그 extra_query는 urllib.parse.urlencode(quote_plus 방식)로
    만들어진다 — 다른 7개 페이지네이션 목록과 같은 인코딩이다(web/views/events.py:248).
    이전에 대체된 인라인 페이저는 Django `|urlencode` 템플릿 필터(quote 방식)를
    썼는데, '+'/공백을 +가 아니라 %2B/%20으로 이스케이프했다. 두 방식 모두
    원본 문자열로 손실 없이 왕복되므로, 아래 '+'/공백 케이스는 특정 인코딩
    리터럴이 아니라 왕복 결과(디코드한 q가 원래 검색어와 같음)를 검증한다 —
    URL 프래그먼트 회피가 핵심인 '#' 케이스만 구체적인 이스케이프 리터럴을
    단언한다."""

    def test_검색어에_해시_기호가_있으면_페이저_링크의_q_값이_URL_인코딩되어_잘리지_않는다(self, make_event):
        for i in range(11):
            make_event(title=f"#콜라보 행사 {i}")

        resp = Client().get("/events/", {"q": "#콜라보"})

        assert resp.status_code == 200
        body = resp.content.decode()
        assert f"q={quote('#콜라보')}" in body
        assert "&q=#" not in body

    def test_검색어에_더하기와_공백이_있으면_페이저_링크의_q_값이_원래_검색어로_보존된다(self, make_event):
        """'+'/공백이 href에 이스케이프되지 않은 채 남으면 안 되고(쿼리 값 안의
        원문 폼인코딩 문자는 의미가 모호하다), 인코더가 %2B/%20을 쓰든 %2B/+를
        쓰든 페이저 링크는 디코드하면 원래 검색어 'a+b c'로 정확히 돌아와야
        한다."""
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
        """selected_region은 검증되지 않은 request.GET.getlist('region')에서
        그대로 페이저에 반영된다 — 원문 '&'/'='가 담긴 값이 href에 추가
        쿼리 파라미터로 재주입되면 안 된다."""
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
class TestEventListDefaultExcludesClosed:
    def test_상태_파라미터가_없으면_기본_행사_목록에서_종료된_행사가_제외된다(self, make_event):
        today = timezone.localdate()
        make_event(
            title="지난달에_끝난_행사",
            start_date=today - timedelta(days=32),
            end_date=today - timedelta(days=1),
        )
        make_event(
            title="다음달에_열리는_행사",
            start_date=today + timedelta(days=30),
            end_date=today + timedelta(days=32),
        )

        resp = Client().get("/events/")

        assert resp.status_code == 200
        body = resp.content.decode()
        assert "다음달에_열리는_행사" in body
        assert "지난달에_끝난_행사" not in body


@pytest.mark.django_db
class TestEventListExplicitStatusGuard:
    """web/views/events.py::event_list는 요청에 status 파라미터가 없거나 빈 경우에만
    status="active"를 주입한다. 이 두 테스트는 그 if-가드 자체를 지킨다:
    사이드바/칩 UI가 보낸 명시적인 status 값은 그대로 통과해야 하고 조용히
    덮어써지면 안 된다."""

    def test_상태를_종료로_지정하면_종료된_행사만_보인다(self, make_event):
        today = timezone.localdate()
        make_event(
            title="지난달에_끝난_행사",
            start_date=today - timedelta(days=32),
            end_date=today - timedelta(days=1),
        )
        make_event(
            title="다음달에_열리는_행사",
            start_date=today + timedelta(days=30),
            end_date=today + timedelta(days=32),
        )

        resp = Client().get("/events/", {"status": "ended"})

        assert resp.status_code == 200
        body = resp.content.decode()
        assert "지난달에_끝난_행사" in body
        assert "다음달에_열리는_행사" not in body

    def test_상태를_전체로_지정하면_종료된_행사도_다시_보인다(self, make_event):
        today = timezone.localdate()
        make_event(
            title="지난달에_끝난_행사",
            start_date=today - timedelta(days=32),
            end_date=today - timedelta(days=1),
        )
        make_event(
            title="다음달에_열리는_행사",
            start_date=today + timedelta(days=30),
            end_date=today + timedelta(days=32),
        )

        resp = Client().get("/events/", {"status": "all"})

        assert resp.status_code == 200
        body = resp.content.decode()
        assert "지난달에_끝난_행사" in body
        assert "다음달에_열리는_행사" in body


@pytest.mark.django_db
class TestEventListGenuinelyEmptyState:
    """진행·예정 목록에 실제로 노출할 행사가 없을 때의 두 서로 다른 시나리오.

    (1) 게시된 행사가 아예 하나도 없는 경우: 정직한 제목을 보여줘야 하고,
    옛 문구("아직 등록된 이벤트가 없어요")는 남아있으면 안 된다.
    (2) 게시된 행사는 있지만 전부 종료돼 기본 필터(진행·예정)에 걸리지 않는
    경우: 카탈로그엔 행사가 있는데 화면은 비어 보이므로, 종료 포함 전체
    보기로 이어지는 회복 링크가 나와야 한다. Given(행사 존재 여부)과 관찰
    결과(회복 링크 유무)가 서로 달라 하나로 묶지 않고 별도 테스트로 나눈다.
    """

    def test_게시된_행사가_전혀_없으면_정직한_빈_상태_제목이_보인다(self):
        resp = Client().get("/events/")

        assert resp.status_code == 200
        body = resp.content.decode()
        assert "진행·예정 이벤트가 없어요" in body
        assert "아직 등록된 이벤트가 없어요" not in body

    def test_기본_필터에서_0건이면_종료_포함_전체_보기_회복_링크가_보인다(self, make_event):
        today = timezone.localdate()
        make_event(
            title="지난달에_끝난_행사",
            start_date=today - timedelta(days=32),
            end_date=today - timedelta(days=1),
        )

        resp = Client().get("/events/")

        assert resp.status_code == 200
        body = resp.content.decode()
        assert "종료 포함 전체 보기" in body

        href = re.search(
            r'<a class="empty-action" href="([^"]*)">종료 포함 전체 보기</a>',
            body,
        )
        assert href, "회복 링크를 찾지 못함"
        query = parse_qs(unescape(href.group(1)).split("?", 1)[1])
        assert query.get("status") == ["all"]


@pytest.mark.django_db
def test_비공개_직접_등록_항목은_공개_행사_목록_페이지에_노출되지_않는다(client, make_user):
    """비공개 PersonalEntry 항목이 공개 목록 HTML에 노출되면 안 된다. API 쪽
    검증은 tests/archive/test_personal_entries_api.py가 맡고, 이 테스트는
    HTML 렌더링만 다룬다(archive의
    test_personal_entry_never_appears_in_public_catalog와 짝을 이룬다).

    archive의 make_entry 픽스처 대신 PersonalEntry.objects.create를 직접
    쓴다: 그 픽스처는 tests/archive/conftest.py에 있는데, pytest의
    디렉터리별 conftest 범위 규칙상 tests/events/에서는 보이지 않는다.
    """
    from archive.models import PersonalEntry

    user = make_user(username="pe-leak")
    PersonalEntry.objects.create(user=user, kind="place", title="PRIVATE_LEAK_CANARY")

    client.force_login(user)
    browse = client.get("/events/")

    assert browse.status_code == 200
    assert "PRIVATE_LEAK_CANARY" not in browse.content.decode()
