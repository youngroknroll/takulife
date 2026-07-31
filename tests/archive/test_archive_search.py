"""아카이브 4개 목록 페이지의 서버 측 q 검색 테스트.

검증 대상 동작:
- ?q=<검색어>는 각 아카이브 목록을 서버에서 필터링한다.
- q는 UserEventStatus/VisitRecord FK를 통해 event.title, event.location_name과 매칭된다.
- q는 같은 FK를 통해 personal_entry.title, personal_entry.location_name과도 매칭된다.
- 다녀온 기록의 q는 short_review와도 매칭된다.
- 직접 등록의 q는 memo, category, work_title과도 매칭된다.
- q와 status= 필터는 AND(교집합)로 결과를 좁힌다.
- 같은 Event를 공유하는 다른 사용자의 기록은 결과에 노출되지 않는다.
- 100자를 넘는 q는 500 없이 받아들여지고 뷰에서 조용히 잘린다.
- 공백만 있는 q는 필터가 없는 것과 같이 동작한다.
- 특수문자(%, &)가 섞인 q는 500을 일으키지 않는다.
"""
import html
import re
from urllib.parse import quote

import pytest

from archive.models import PersonalEntry

pytestmark = pytest.mark.web


# ---------------------------------------------------------------------------
# 상태 페이지 (/archive/ 및 /archive/statuses/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestStatusPagesQFilter:
    """q는 /archive/와 /archive/statuses/의 status_rows를 서버에서 함께 필터링한다."""

    def test_전체_보기에서_검색어가_행사_제목과_일치하면_해당_행사만_노출된다(self, user_client, make_event, make_status):
        user, client = user_client()
        match_event = make_event(title="매칭 이벤트", location_name="서울")
        no_match = make_event(title="다른 이벤트", location_name="부산")
        make_status(user, event=match_event, status="planned")
        make_status(user, event=no_match, status="planned")

        resp = client.get("/archive/?q=매칭")

        assert resp.status_code == 200
        titles = [row["subject"]["title"] for row in resp.context["status_rows"]]
        assert "매칭 이벤트" in titles
        assert "다른 이벤트" not in titles

    def test_나의_일정에서_검색어가_행사_장소와_일치하면_해당_행사만_노출된다(self, user_client, make_event, make_status):
        user, client = user_client()
        match_event = make_event(title="이벤트A", location_name="홍대 카페")
        no_match = make_event(title="이벤트B", location_name="강남")
        make_status(user, event=match_event, status="planned")
        make_status(user, event=no_match, status="planned")

        resp = client.get("/archive/statuses/?q=홍대")

        assert resp.status_code == 200
        titles = [row["subject"]["title"] for row in resp.context["status_rows"]]
        assert "이벤트A" in titles
        assert "이벤트B" not in titles

    def test_나의_일정에서_검색어가_직접_등록_항목_제목과_일치하면_해당_항목만_노출된다(self, user_client, make_status, make_entry):
        user, client = user_client()
        entry_match = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="매칭 카페")
        entry_no = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="다른 항목")
        make_status(user, personal_entry=entry_match, status="planned")
        make_status(user, personal_entry=entry_no, status="planned")

        resp = client.get("/archive/statuses/?q=매칭")

        assert resp.status_code == 200
        titles = [row["subject"]["title"] for row in resp.context["status_rows"]]
        assert "매칭 카페" in titles
        assert "다른 항목" not in titles

    def test_나의_일정에서_검색어가_직접_등록_항목_장소와_일치하면_해당_항목만_노출된다(self, user_client, make_status, make_entry):
        user, client = user_client()
        entry_match = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="A항목", location_name="신촌 골목")
        entry_no = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="B항목", location_name="이태원")
        make_status(user, personal_entry=entry_match, status="planned")
        make_status(user, personal_entry=entry_no, status="planned")

        resp = client.get("/archive/statuses/?q=신촌")

        titles = [row["subject"]["title"] for row in resp.context["status_rows"]]
        assert "A항목" in titles
        assert "B항목" not in titles

    def test_나의_일정에서_상태_필터와_검색어를_함께_적용하면_둘_다_일치하는_행사만_남는다(self, user_client, make_event, make_status):
        """q + status=planned → 두 필터를 모두 만족하는 행만 남는다."""
        user, client = user_client()
        # 예정 상태이고 제목도 q와 일치
        match_plan = make_event(title="매칭 계획")
        make_status(user, event=match_plan, status="planned")
        # 예정 상태이지만 제목은 q와 불일치
        no_match_plan = make_event(title="다른 계획")
        make_status(user, event=no_match_plan, status="planned")
        # 제목은 q와 일치하지만 상태가 방문완료(예정 아님)
        match_visit = make_event(title="매칭 방문")
        make_status(user, event=match_visit, status="visited")

        resp = client.get("/archive/statuses/?status=planned&q=매칭")

        assert resp.status_code == 200
        titles = [row["subject"]["title"] for row in resp.context["status_rows"]]
        assert "매칭 계획" in titles
        assert "다른 계획" not in titles
        assert "매칭 방문" not in titles

    def test_나의_일정에_검색어를_전달하면_검색_상태가_컨텍스트에_기록된다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/statuses/?q=검색어")

        assert resp.context["q"] == "검색어"
        assert resp.context["has_query"] is True

    def test_전체_보기에_검색어를_전달하면_검색_상태가_컨텍스트에_기록된다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/?q=test")

        assert resp.context["q"] == "test"
        assert resp.context["has_query"] is True

    def test_나의_일정_페이저는_상태_필터와_검색어를_모두_유지한다(self, user_client, make_event, make_status):
        user, client = user_client()
        # 2페이지가 생기도록 충분한 행을 만든다
        for i in range(7):
            ev = make_event(title=f"매칭 {i:02d}")
            make_status(user, event=ev, status="planned")

        resp = client.get("/archive/statuses/?status=planned&q=매칭")

        assert resp.status_code == 200
        pager_query = resp.context["pager_query"]
        assert "status=planned" in pager_query
        assert "q=" in pager_query

    def test_전체_보기에서_검색어가_있을_때_상태_칩_링크는_검색어를_유지한다(self, user_client):
        """core/views.py는 이미 search_suffix를 context에 계산해 두지만(838,845)
        index.html이 칩 href에서 이를 쓰지 않은 것이 버그였다(2026-07-23 v2
        계획서 §동반 수정 1). 검색 중에 상태 칩을 눌러도 검색어가 조용히
        사라지면 안 된다."""
        _, client = user_client()

        resp = client.get("/archive/?q=test")

        # Django가 href 속성의 `{{ search_suffix }}`를 자동 이스케이프해 원본
        # HTML에는 `&amp;`로 남는다(브라우저가 다시 `&`로 해석 — core/views.py
        # :836-837 참고). 언이스케이프하지 않으면 이 단언이 `&`를 찾지 못한다.
        content = html.unescape(resp.content.decode())
        assert 'href="/archive/?status=planned&q=test"' in content

    def test_나의_일정에서_검색어가_있을_때_상태_칩_링크는_검색어를_유지한다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/statuses/?q=test")

        # 위 언이스케이프 설명 참고 — 자동 이스케이프가 `&`를 `&amp;`로 바꾼다.
        content = html.unescape(resp.content.decode())
        assert 'href="/archive/statuses/?status=planned&q=test"' in content


# ---------------------------------------------------------------------------
# 다녀온 기록 페이지 (/archive/visits/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestVisitsPageQFilter:
    """q는 short_review를 포함해 /archive/visits/의 visit_rows를 필터링한다."""

    def test_다녀온_기록에서_검색어가_행사_제목과_일치하면_해당_방문만_노출된다(self, user_client, make_event, make_visit):
        user, client = user_client()
        match_ev = make_event(title="매칭 팝업")
        no_match_ev = make_event(title="다른 팝업")
        make_visit(user, event=match_ev, visited_on="2026-06-01")
        make_visit(user, event=no_match_ev, visited_on="2026-06-02")

        resp = client.get("/archive/visits/?q=매칭")

        assert resp.status_code == 200
        titles = [row["subject"]["title"] for row in resp.context["visit_rows"]]
        assert "매칭 팝업" in titles
        assert "다른 팝업" not in titles

    def test_다녀온_기록에서_검색어가_행사_장소와_일치하면_해당_방문만_노출된다(self, user_client, make_event, make_visit):
        user, client = user_client()
        match_ev = make_event(title="팝업A", location_name="성수 거리")
        no_match_ev = make_event(title="팝업B", location_name="강남역")
        make_visit(user, event=match_ev, visited_on="2026-06-01")
        make_visit(user, event=no_match_ev, visited_on="2026-06-02")

        resp = client.get("/archive/visits/?q=성수")

        titles = [row["subject"]["title"] for row in resp.context["visit_rows"]]
        assert "팝업A" in titles
        assert "팝업B" not in titles

    def test_다녀온_기록에서_검색어가_한줄_후기와_일치하면_해당_방문만_노출된다(self, user_client, make_event, make_visit):
        user, client = user_client()
        ev_with_review = make_event(title="행사A")
        ev_no_match = make_event(title="행사B")
        make_visit(user, event=ev_with_review, visited_on="2026-06-01", short_review="굉장히 재미있었다")
        make_visit(user, event=ev_no_match, visited_on="2026-06-02", short_review="별로")

        resp = client.get("/archive/visits/?q=굉장히")

        titles = [row["subject"]["title"] for row in resp.context["visit_rows"]]
        assert "행사A" in titles
        assert "행사B" not in titles

    def test_다녀온_기록에서_검색어가_직접_등록_항목_제목과_일치하면_해당_방문만_노출된다(self, user_client, make_visit, make_entry):
        user, client = user_client()
        entry_match = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="비공식 매칭")
        entry_no = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="비공식 아님")
        make_visit(user, personal_entry=entry_match, visited_on="2026-06-01")
        make_visit(user, personal_entry=entry_no, visited_on="2026-06-02")

        resp = client.get("/archive/visits/?q=매칭")

        titles = [row["subject"]["title"] for row in resp.context["visit_rows"]]
        assert "비공식 매칭" in titles
        assert "비공식 아님" not in titles

    def test_다녀온_기록에서_비공식_필터와_검색어를_함께_적용하면_둘_다_일치하는_방문만_남는다(self, user_client, make_event, make_visit, make_entry):
        """filter=unofficial AND q → q와 일치하는 비공식 행만 남는다."""
        user, client = user_client()
        # 비공식이고 q와 일치
        entry_match = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="비공식 매칭")
        make_visit(user, personal_entry=entry_match, visited_on="2026-06-03")
        # 제목은 일치하지만 공식이라 filter=unofficial에서 제외됨
        official_ev = make_event(title="공식 매칭")
        make_visit(user, event=official_ev, visited_on="2026-06-02")
        # 비공식이지만 q와 불일치
        entry_no = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="비공식 아님")
        make_visit(user, personal_entry=entry_no, visited_on="2026-06-01")

        resp = client.get("/archive/visits/?filter=unofficial&q=매칭")

        assert resp.status_code == 200
        titles = [row["subject"]["title"] for row in resp.context["visit_rows"]]
        assert "비공식 매칭" in titles
        assert "공식 매칭" not in titles
        assert "비공식 아님" not in titles

    def test_다녀온_기록에_검색어를_전달하면_검색_상태가_컨텍스트에_기록된다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/visits/?q=찾기")

        assert resp.context["q"] == "찾기"
        assert resp.context["has_query"] is True


# ---------------------------------------------------------------------------
# 직접 등록 페이지 (/archive/personal/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestItemsPageQFilter:
    """q는 /archive/personal/의 entry_rows를 필터링한다."""

    def test_직접_등록에서_검색어가_항목_제목과_일치하면_해당_항목만_노출된다(self, user_client, make_entry):
        user, client = user_client()
        make_entry(user, kind=PersonalEntry.Kind.PLACE, title="매칭 항목")
        make_entry(user, kind=PersonalEntry.Kind.PLACE, title="다른 항목")

        resp = client.get("/archive/personal/?q=매칭")

        assert resp.status_code == 200
        titles = [row["entry"].title for row in resp.context["entry_rows"]]
        assert "매칭 항목" in titles
        assert "다른 항목" not in titles

    def test_직접_등록에서_검색어가_메모와_일치하면_해당_항목만_노출된다(self, user_client, make_entry):
        user, client = user_client()
        make_entry(user, kind=PersonalEntry.Kind.PLACE, title="A", memo="특별한 내용")
        make_entry(user, kind=PersonalEntry.Kind.PLACE, title="B", memo="보통 내용")

        resp = client.get("/archive/personal/?q=특별한")

        titles = [row["entry"].title for row in resp.context["entry_rows"]]
        assert "A" in titles
        assert "B" not in titles

    def test_직접_등록에서_검색어가_장소와_일치하면_해당_항목만_노출된다(self, user_client, make_entry):
        user, client = user_client()
        make_entry(user, kind=PersonalEntry.Kind.PLACE, title="A", location_name="신촌")
        make_entry(user, kind=PersonalEntry.Kind.PLACE, title="B", location_name="강남")

        resp = client.get("/archive/personal/?q=신촌")

        titles = [row["entry"].title for row in resp.context["entry_rows"]]
        assert "A" in titles
        assert "B" not in titles

    def test_직접_등록에서_검색어가_원작_제목과_일치하면_해당_항목만_노출된다(self, user_client, make_entry):
        user, client = user_client()
        make_entry(user, kind="goods", title="A", work_title="원피스 콜라보")
        make_entry(user, kind="goods", title="B", work_title="블리치")

        resp = client.get("/archive/personal/?q=원피스")

        titles = [row["entry"].title for row in resp.context["entry_rows"]]
        assert "A" in titles
        assert "B" not in titles

    def test_직접_등록에서_검색어가_카테고리와_일치하면_해당_항목만_노출된다(self, user_client, make_entry):
        user, client = user_client()
        make_entry(user, kind=PersonalEntry.Kind.PLACE, title="A", category="팝업스토어")
        make_entry(user, kind=PersonalEntry.Kind.PLACE, title="B", category="카페")

        resp = client.get("/archive/personal/?q=팝업")

        titles = [row["entry"].title for row in resp.context["entry_rows"]]
        assert "A" in titles
        assert "B" not in titles


# ---------------------------------------------------------------------------
# 교차 관심사: 사용자 격리, q 정규화, 특수문자
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestArchiveSearchIsolation:
    """같은 Event를 공유하는 다른 사용자의 기록은 q 결과에 나타나면 안 된다."""

    def test_나의_일정_검색은_다른_사용자의_기록을_노출하지_않는다(self, user_client, make_event, make_status):
        user_a, client_a = user_client(username="userA")
        user_b, _ = user_client(username="userB")

        shared_event = make_event(title="공유 이벤트")
        make_status(user_a, event=shared_event, status="planned")
        make_status(user_b, event=shared_event, status="planned")

        resp = client_a.get("/archive/statuses/?q=공유")

        assert resp.status_code == 200
        # 정확히 1행만 보여야 한다 — user B가 아닌 user A 자신의 상태.
        assert resp.context["page_obj"].paginator.count == 1

    def test_다녀온_기록_검색은_다른_사용자의_기록을_노출하지_않는다(self, user_client, make_event, make_visit):
        user_a, client_a = user_client(username="visitorA")
        user_b, _ = user_client(username="visitorB")

        shared_event = make_event(title="공유 팝업")
        make_visit(user_a, event=shared_event, visited_on="2026-06-01")
        make_visit(user_b, event=shared_event, visited_on="2026-06-01")

        resp = client_a.get("/archive/visits/?q=공유")

        assert resp.status_code == 200
        assert resp.context["page_obj"].paginator.count == 1


@pytest.mark.django_db
class TestArchiveSearchErrorElementSharedStyle:
    """아카이브 검색 부분템플릿의 오류 문구가 공용 토큰 기반 .inline-error
    클래스(auth.css의 .field-error와 같은 토큰 사용) 대신 하드코딩 인라인
    스타일(#b91c1c/0.82rem/4px)을 쓰던 문제 — 렌더된 마크업이 인라인 스타일
    없이 공용 클래스로 옮겨졌는지 검증한다."""

    def test_전체_보기_검색_오류_문구는_공용_inline_error_스타일_클래스를_사용한다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/")

        assert resp.status_code == 200
        content = resp.content.decode()
        assert '<p id="archive-search-error" class="inline-error" aria-live="polite"></p>' in content


@pytest.mark.django_db
class TestArchiveSearchClearLink:
    """아카이브 검색 부분템플릿의 지우기 링크는 항상 페이지 경로만 가리키면
    안 되고, 페이지에 활성화된 검색 외 필터(status/filter)로 돌아가야 한다 —
    그렇지 않으면 지우기를 눌렀을 때 q뿐 아니라 사용자가 선택한 상태/필터도
    조용히 사라진다."""

    def _clear_href(self, content):
        # 속성 순서에 무관하게: class로 anchor 태그를 찾은 뒤 같은 태그에서
        # href를 뽑는다.
        tag_match = re.search(r'<a\b[^>]*class="archive-search-clear"[^>]*>', content)
        assert tag_match, content
        href_match = re.search(r'href="([^"]*)"', tag_match.group(0))
        assert href_match, tag_match.group(0)
        return href_match.group(1)

    def test_검색_지우기_링크는_활성_상태_필터를_유지한다(self, user_client):
        """원래 버그의 회귀 케이스: 지우기 href가 항상 request.path로만
        축소되어 활성 상태 필터가 사라졌었다."""
        _, client = user_client()

        resp = client.get("/archive/statuses/?status=planned&q=여름")

        assert resp.status_code == 200
        assert self._clear_href(resp.content.decode()) == "/archive/statuses/?status=planned"

    def test_상태_필터가_없으면_검색_지우기_링크는_기본_경로만_가리킨다(self, user_client):
        """특성화 테스트: 필터가 없을 때 동작(href == request.path)을 고정해
        이후 변경이 조용히 바꾸지 못하게 한다."""
        _, client = user_client()

        resp = client.get("/archive/statuses/?q=여름")

        assert resp.status_code == 200
        assert self._clear_href(resp.content.decode()) == "/archive/statuses/"

    def test_숨은_필터_이름을_넘기지_않는_페이지의_검색_지우기_링크는_기본_경로만_가리킨다(self, user_client):
        """특성화 테스트: hidden_name/hidden_value를 전혀 넘기지 않는 페이지
        (personal_entries.html)는 경로만 있는 지우기 링크를 렌더한다."""
        _, client = user_client()

        resp = client.get("/archive/personal/?q=여름")

        assert resp.status_code == 200
        assert self._clear_href(resp.content.decode()) == "/archive/personal/"

    def test_다녀온_기록의_검색_지우기_링크는_한글_필터_값을_URL_인코딩해_유지한다(self, user_client, make_event, make_visit):
        """visits.html의 hidden_name="filter"는 한글 라벨 값(cat:<라벨>)을
        갖는다 — 지우기 링크는 이를 URL 인코딩해야 하며, 원본 비ASCII 값을
        href에 그대로 넣으면 안 된다."""
        user, client = user_client()
        event = make_event(title="팝업 행사", category="popup_store")
        make_visit(user, event=event, visited_on="2026-06-01")

        resp = client.get("/archive/visits/?filter=cat:팝업스토어&q=여름")

        assert resp.status_code == 200
        href = self._clear_href(resp.content.decode())
        assert href == f"/archive/visits/?filter={quote('cat:팝업스토어')}"


@pytest.mark.django_db
class TestQNormalisation:
    """q는 필터링 전에 strip()[:100]으로 정규화된다."""

    def test_공백만_있는_검색어는_필터_없이_전체_결과를_보여준다(self, user_client, make_entry):
        user, client = user_client()
        make_entry(user, kind=PersonalEntry.Kind.PLACE, title="항목 A")
        make_entry(user, kind=PersonalEntry.Kind.PLACE, title="항목 B")

        resp = client.get("/archive/personal/?q=   ")

        assert resp.status_code == 200
        assert resp.context["q"] == ""
        assert resp.context["has_query"] is False
        # 필터가 적용되지 않아 모든 항목이 그대로 반환된다
        assert resp.context["page_obj"].paginator.count == 2

    def test_긴_검색어는_잘려서_오류_없이_처리된다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/personal/?q=" + "A" * 200)

        assert resp.status_code == 200

    def test_전체_보기_검색에_특수문자가_있어도_서버_오류가_나지_않는다(self, user_client):
        _, client = user_client()

        for special_q in ("a%b", "x&y=z", "<script>"):
            resp = client.get(f"/archive/?q={special_q}")
            assert resp.status_code == 200, f"500 on q={special_q!r}"

    def test_다녀온_기록_검색에_특수문자가_있어도_서버_오류가_나지_않는다(self, user_client):
        _, client = user_client()

        for special_q in ("a%b", "x&y=z", "<script>"):
            resp = client.get(f"/archive/visits/?q={special_q}")
            assert resp.status_code == 200, f"500 on q={special_q!r}"
