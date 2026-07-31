"""스태프 전용 드래프트 HTML 뷰(목록/상세) 검증."""
import re

import pytest

from drafts.models import EventDraft

pytestmark = pytest.mark.web


@pytest.mark.django_db
class TestEventDraftsListView:
    def test_드래프트_목록_페이지는_등록된_드래프트_행을_렌더링한다(self, staff_client, make_draft):
        make_draft("https://example.com/a", extracted_title="드래프트 A", extracted_category="popup_store")
        make_draft("https://example.com/b", extracted_title="드래프트 B")

        _, client = staff_client()
        resp = client.get("/staff/drafts/")

        assert resp.status_code == 200
        body = resp.content.decode()
        assert "드래프트 A" in body
        assert "드래프트 B" in body


def _seed_drafts(make_draft, count, status=EventDraft.ReviewStatus.PENDING, start=0):
    for i in range(start, start + count):
        make_draft(f"https://example.com/{status}-{i}", review_status=status)


@pytest.mark.django_db
class TestEventDraftsListFilterPagination:
    """/staff/drafts/ 상태 필터 + 페이지네이션."""

    def test_드래프트_목록_첫_페이지는_페이지_크기만큼만_보여주고_페이저를_포함한다(self, staff_client, make_draft):
        from drafts.queries import DRAFT_LISTING_PAGE_SIZE

        _seed_drafts(make_draft, DRAFT_LISTING_PAGE_SIZE + 1)

        _, client = staff_client()
        resp = client.get("/staff/drafts/")

        assert resp.status_code == 200
        page_obj = resp.context["page_obj"]
        assert page_obj.paginator.count == DRAFT_LISTING_PAGE_SIZE + 1
        assert len(page_obj.object_list) == DRAFT_LISTING_PAGE_SIZE
        assert page_obj.has_other_pages() is True

    def test_드래프트_건수가_한_페이지_이내면_페이저가_없다(self, staff_client, make_draft):
        from drafts.queries import DRAFT_LISTING_PAGE_SIZE

        _seed_drafts(make_draft, DRAFT_LISTING_PAGE_SIZE)

        _, client = staff_client()
        resp = client.get("/staff/drafts/")

        assert resp.context["page_obj"].has_other_pages() is False

    def test_드래프트_목록_두번째_페이지는_남은_건수를_보여주고_첫_페이지와_겹치지_않는다(self, staff_client, make_draft):
        from drafts.queries import DRAFT_LISTING_PAGE_SIZE

        _seed_drafts(make_draft, DRAFT_LISTING_PAGE_SIZE + 1)

        _, client = staff_client()
        first = client.get("/staff/drafts/")
        second = client.get("/staff/drafts/?page=2")

        assert second.status_code == 200
        second_page = second.context["page_obj"]
        assert second_page.number == 2
        assert len(second_page.object_list) == 1
        first_ids = [row["draft"].id for row in first.context["draft_rows"]]
        second_ids = [row["draft"].id for row in second.context["draft_rows"]]
        assert set(first_ids).isdisjoint(second_ids)

    @pytest.mark.parametrize(
        "page_value",
        ["abc", "9999", "0"],
        ids=["문자열_abc", "범위를_초과하는_9999", "0"],
    )
    def test_잘못된_page_값을_주어도_200을_응답한다(self, staff_client, page_value, make_draft):
        _seed_drafts(make_draft, 21)

        _, client = staff_client()
        resp = client.get(f"/staff/drafts/?page={page_value}")

        assert resp.status_code == 200

    def test_상태_필터를_적용하면_일치하는_드래프트만_보여준다(self, staff_client, make_draft):
        pending = make_draft("https://example.com/pending-1", review_status=EventDraft.ReviewStatus.PENDING)
        make_draft("https://example.com/approved-1", review_status=EventDraft.ReviewStatus.APPROVED)
        make_draft("https://example.com/rejected-1", review_status=EventDraft.ReviewStatus.REJECTED)

        _, client = staff_client()
        resp = client.get("/staff/drafts/?status=pending")

        assert resp.status_code == 200
        rows = resp.context["draft_rows"]
        assert [row["draft"].id for row in rows] == [pending.id]

    def test_상태_필터가_없으면_전체_드래프트를_id_내림차순으로_보여준다(self, staff_client, make_draft):
        first = make_draft("https://example.com/x-1")
        second = make_draft("https://example.com/x-2")

        _, client = staff_client()
        resp = client.get("/staff/drafts/")

        rows = resp.context["draft_rows"]
        assert [row["draft"].id for row in rows] == [second.id, first.id]

    def test_알_수_없는_상태_값은_전체_보기로_대체된다(self, staff_client, make_draft):
        make_draft("https://example.com/y-1")

        _, client = staff_client()
        resp = client.get("/staff/drafts/?status=garbage")

        assert resp.status_code == 200
        assert resp.context["selected_status"] == ""

    def test_드래프트_목록_페이저는_상태_필터를_유지한다(self, staff_client, make_draft):
        _seed_drafts(make_draft, 21, status=EventDraft.ReviewStatus.PENDING)

        _, client = staff_client()
        resp = client.get("/staff/drafts/?status=pending")

        assert resp.status_code == 200
        assert resp.context["pager_query"] == "&status=pending"
        assert b"?page=2&amp;status=pending" in resp.content

    def test_드래프트_통계_카드는_필터링된_부분집합이_아닌_전체_건수를_보여준다(self, staff_client, make_draft):
        _seed_drafts(make_draft, 2, status=EventDraft.ReviewStatus.PENDING)
        _seed_drafts(make_draft, 3, status=EventDraft.ReviewStatus.APPROVED)
        _seed_drafts(make_draft, 1, status=EventDraft.ReviewStatus.REJECTED)

        _, client = staff_client()
        resp = client.get("/staff/drafts/?status=pending")

        assert resp.status_code == 200
        stats = resp.context["stats"]
        assert stats["pending"] == 2
        assert stats["approved"] == 3
        assert stats["rejected"] == 1

    def test_상태_필터가_적용된_상태에서도_페이지_경계를_넘어_정렬_순서가_유지된다(self, staff_client, make_draft):
        _seed_drafts(make_draft, 21, status=EventDraft.ReviewStatus.PENDING)

        _, client = staff_client()
        resp = client.get("/staff/drafts/?status=pending&page=2")

        assert resp.status_code == 200
        rows = resp.context["draft_rows"]
        ids = [row["draft"].id for row in rows]
        assert ids == sorted(ids, reverse=True)

    def test_드래프트가_전혀_없으면_등록_안내_빈_상태를_보여준다(self, staff_client):
        _, client = staff_client()
        resp = client.get("/staff/drafts/")

        assert resp.status_code == 200
        assert "등록된 드래프트가 없습니다" in resp.content.decode()

    def test_선택한_상태에_해당하는_드래프트가_없으면_해당_상태_빈_상태_문구를_보여준다(self, staff_client, make_draft):
        make_draft("https://example.com/only-pending", review_status=EventDraft.ReviewStatus.PENDING)

        _, client = staff_client()
        resp = client.get("/staff/drafts/?status=rejected")

        assert resp.status_code == 200
        body = resp.content.decode()
        assert "해당 상태의 드래프트가 없습니다" in body
        assert "전체 보기" in body
        assert "등록된 드래프트가 없습니다" not in body

    def test_상태_필터가_있어도_DB가_완전히_비어있으면_등록_안내_빈_상태를_보여준다(self, staff_client):
        _, client = staff_client()
        resp = client.get("/staff/drafts/?status=pending")

        assert resp.status_code == 200
        assert "등록된 드래프트가 없습니다" in resp.content.decode()


@pytest.mark.django_db
class TestEventDraftsListStatusChipLabel:
    """목록의 상태 칩은 저장된 enum이 아니라 한국어 문구로 보여야 한다.

    판정 직후 칩을 갱신하는 쪽은 draft_bulk.js이고 그건 브라우저에서만
    도는 코드다 — 여기서는 서버가 처음 그리는 문구만 고정한다.
    """

    def test_판정된_드래프트의_상태_칩은_원시_enum이_아니라_한국어로_보인다(
        self, staff_client, make_draft
    ):
        make_draft(
            "https://example.com/approved-chip",
            review_status=EventDraft.ReviewStatus.APPROVED,
        )

        _, client = staff_client()
        resp = client.get("/staff/drafts/")

        assert resp.status_code == 200
        body = resp.content.decode()
        assert "승인됨" in body
        # 칩 자리에 enum 문자열이 그대로 노출되면 안 된다.
        assert ">approved<" not in body


@pytest.mark.django_db
class TestEventDraftListWarningBadges:
    """B1: 제목·지역·기간이 빠진 드래프트는 목록 행에 경고 태그가 붙는다.

    이미 가져온 필드(extracted_title/raw_title/extracted_region/
    extracted_start_date/extracted_end_date)만으로 파생하며 별도 조회가
    없다.
    """

    def test_제목_지역_기간이_모두_있으면_경고_태그가_없다(self, staff_client, make_draft):
        make_draft(
            "https://example.com/complete",
            extracted_title="완전한 드래프트",
            extracted_region="seoul",
            extracted_start_date="2026-08-01",
            extracted_end_date="2026-08-10",
        )

        _, client = staff_client()
        resp = client.get("/staff/drafts/")

        assert resp.context["draft_rows"][0]["warning_badges"] == []

    def test_제목이_없으면_제목_없음_경고가_붙는다(self, staff_client, make_draft):
        make_draft("https://example.com/no-title")

        _, client = staff_client()
        resp = client.get("/staff/drafts/")

        assert "제목 없음" in resp.context["draft_rows"][0]["warning_badges"]

    def test_raw_title만_있어도_제목_없음_경고가_붙지_않는다(self, staff_client, make_draft):
        make_draft("https://example.com/raw-title-only", raw_title="원문 제목")

        _, client = staff_client()
        resp = client.get("/staff/drafts/")

        assert "제목 없음" not in resp.context["draft_rows"][0]["warning_badges"]

    def test_지역이_없으면_지역_없음_경고가_붙는다(self, staff_client, make_draft):
        make_draft("https://example.com/no-region", extracted_title="지역 없는 드래프트")

        _, client = staff_client()
        resp = client.get("/staff/drafts/")

        assert "지역 없음" in resp.context["draft_rows"][0]["warning_badges"]

    def test_시작일이나_종료일이_없으면_기간_없음_경고가_붙는다(self, staff_client, make_draft):
        make_draft(
            "https://example.com/no-period",
            extracted_title="기간 없는 드래프트",
            extracted_start_date="2026-08-01",
        )

        _, client = staff_client()
        resp = client.get("/staff/drafts/")

        assert "기간 없음" in resp.context["draft_rows"][0]["warning_badges"]


@pytest.mark.django_db
class TestEventDraftDetailView:
    def test_존재하는_드래프트_상세는_카테고리_지역_라벨을_사람이_읽을_수_있게_보여준다(self, staff_client, make_draft):
        draft = make_draft("https://example.com/c", extracted_title="상세 드래프트", extracted_category="popup_store", extracted_region="seoul")

        _, client = staff_client()
        resp = client.get(f"/staff/drafts/{draft.id}/")

        assert resp.status_code == 200
        assert resp.context["draft"] == draft
        assert resp.context["is_pending"] is True
        assert resp.context["category_label"] == "팝업스토어"
        assert resp.context["region_label"] == "서울"

    def test_존재하지_않는_드래프트_상세는_찾을_수_없음_안내를_보여준다(self, staff_client):
        _, client = staff_client()
        resp = client.get("/staff/drafts/999999/")

        assert resp.status_code == 200
        assert resp.context["draft_not_found"] is True


@pytest.mark.django_db
class TestEventDraftPreapprovalChecks:
    """B2: 승인 전 체크 — EventDraft 전용 규칙. Event의 _event_quality_badges와는
    다른 규칙 집합이다(드래프트엔 poster_image가 없다).
    """

    def test_모든_체크를_통과하면_전부_통과로_표시된다(self, staff_client, make_draft):
        draft = make_draft(
            "https://example.com/preapproval-ok",
            extracted_title="완전한 드래프트",
            extracted_category="popup_store",
            extracted_region="seoul",
        )

        _, client = staff_client()
        resp = client.get(f"/staff/drafts/{draft.id}/")

        checks = {c["key"]: c["passed"] for c in resp.context["preapproval_checks"]}
        assert checks == {
            "title": True,
            "official_url": True,
            "official_url_unique": True,
            "category": True,
            "region": True,
        }

    def test_제목이_없으면_제목_체크가_실패로_표시된다(self, staff_client, make_draft):
        draft = make_draft("https://example.com/preapproval-no-title")

        _, client = staff_client()
        resp = client.get(f"/staff/drafts/{draft.id}/")

        checks = {c["key"]: c["passed"] for c in resp.context["preapproval_checks"]}
        assert checks["title"] is False

    def test_공식_url이_이미_게시된_이벤트와_중복되면_중복_체크가_실패로_표시된다(self, staff_client, make_draft, make_event):
        make_event(official_url="https://example.com/preapproval-dup")
        draft = make_draft(
            "https://example.com/preapproval-dup", extracted_title="중복 드래프트"
        )

        _, client = staff_client()
        resp = client.get(f"/staff/drafts/{draft.id}/")

        checks = {c["key"]: c["passed"] for c in resp.context["preapproval_checks"]}
        assert checks["official_url_unique"] is False


@pytest.mark.django_db
def test_비로그인_사용자의_드래프트_목록_접근은_로그인_페이지로_리다이렉트된다(client):
    response = client.get("/staff/drafts/")

    assert response.status_code == 302
    assert response.url.startswith("/accounts/login/")


@pytest.mark.django_db
def test_비로그인_사용자의_드래프트_상세_접근은_로그인_페이지로_리다이렉트된다(client):
    response = client.get("/staff/drafts/1/")

    assert response.status_code == 302
    assert response.url.startswith("/accounts/login/")


@pytest.mark.django_db
class TestDraftConfidenceDisplay:
    """confidence는 0~1로 저장된다(LLM_ESCALATION_CONFIDENCE_THRESHOLD=0.6이 같은 척도).

    화면이 이를 0~100으로 읽으면 0.83이 "1%"로 나오고 색 등급도 늘 최하로 떨어진다.
    """

    def test_목록의_신뢰도_배지는_백분율과_등급을_함께_보여준다(self, staff_client, make_draft):
        make_draft("https://example.com/hi", extracted_title="높은 신뢰도", confidence=0.83)

        _, client = staff_client()
        resp = client.get("/staff/drafts/")

        assert resp.status_code == 200
        body = resp.content.decode()
        assert "83%" in body
        assert "1%" not in body
        assert "queue-conf-badge is-high" in body

    def test_상세의_신뢰도도_백분율로_보여준다(self, staff_client, make_draft):
        draft = make_draft("https://example.com/lo", extracted_title="낮은 신뢰도", confidence=0.42)

        _, client = staff_client()
        resp = client.get(f"/staff/drafts/{draft.id}/")

        assert resp.status_code == 200
        assert "신뢰도 42%" in resp.content.decode()


@pytest.mark.django_db
def test_선택된_드래프트_상태_탭만_적용됨으로_노출된다(staff_client, make_draft):
    """클래스 is-active는 보조기술에 아무것도 전달하지 않는다."""
    make_draft("https://example.com/t", extracted_title="탭 확인용")

    _, client = staff_client()
    resp = client.get("/staff/drafts/?status=pending")

    assert resp.status_code == 200
    body = resp.content.decode()
    tabs = re.findall(r'<a class="queue-tab[^"]*"[^>]*>', body)
    assert len(tabs) == 4, tabs
    current = [t for t in tabs if 'aria-current="true"' in t]
    assert len(current) == 1, tabs
    assert "적용됨" in current[0]
