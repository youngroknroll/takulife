"""세 아카이브 SSR 목록 페이지의 페이지네이션 테스트.

검증 대상: 기록장(/archive/)은 저장한 행사를 10건씩, 예정 목록
(/archive/statuses/)은 같은 상태 목록을 5건씩 ?status= 필터를 유지한 채,
방문 기록(/archive/visits/)은 타임라인을 5건씩 페이지네이션하며 요약 카드
(누적 방문/메모 있음)는 전체 레코드 기준을 계속 보고한다.
"""
import pytest

from archive.models import UserEventStatus

pytestmark = pytest.mark.web


@pytest.mark.django_db
class TestArchiveRecordPagination:
    """기록장 (/archive/) — 저장한 행사, 10건씩."""

    def test_전체_보기_첫_페이지는_열_건까지만_보여준다(self, user_client, make_statuses):
        user, client = user_client()
        make_statuses(user, 12)

        resp = client.get("/archive/")

        assert resp.status_code == 200
        page_obj = resp.context["page_obj"]
        assert page_obj.paginator.count == 12
        assert page_obj.paginator.num_pages == 2
        assert page_obj.number == 1
        assert len(page_obj.object_list) == 10
        assert len(resp.context["status_rows"]) == 10
        assert resp.context["has_statuses"] is True

    def test_전체_보기_두번째_페이지는_남은_건수를_보여준다(self, user_client, make_statuses):
        user, client = user_client()
        make_statuses(user, 12)

        resp = client.get("/archive/?page=2")

        assert resp.status_code == 200
        page_obj = resp.context["page_obj"]
        assert page_obj.number == 2
        assert len(page_obj.object_list) == 2

    def test_전체_보기_건수가_한_페이지_이내면_페이저가_없다(self, user_client, make_statuses):
        user, client = user_client()
        make_statuses(user, 8)

        resp = client.get("/archive/")

        assert resp.context["page_obj"].paginator.num_pages == 1
        assert resp.context["page_obj"].has_other_pages() is False


@pytest.mark.django_db
class TestArchiveStatusesPagination:
    """예정 목록 (/archive/statuses/) — 5건씩, 필터 유지."""

    def test_나의_일정_첫_페이지는_다섯_건까지만_보여준다(self, user_client, make_statuses):
        user, client = user_client()
        make_statuses(user, 7)

        resp = client.get("/archive/statuses/")

        assert resp.status_code == 200
        page_obj = resp.context["page_obj"]
        assert page_obj.paginator.count == 7
        assert page_obj.paginator.num_pages == 2
        assert len(page_obj.object_list) == 5

    def test_나의_일정_두번째_페이지는_남은_건수를_보여준다(self, user_client, make_statuses):
        user, client = user_client()
        make_statuses(user, 7)

        resp = client.get("/archive/statuses/?page=2")

        assert resp.context["page_obj"].number == 2
        assert len(resp.context["page_obj"].object_list) == 2

    def test_나의_일정_페이저_링크는_활성_상태_필터를_유지한다(self, user_client, make_statuses):
        user, client = user_client()
        make_statuses(user, 7, status=UserEventStatus.Status.PLANNED)

        resp = client.get("/archive/statuses/?status=planned")

        assert resp.status_code == 200
        # 필터 꼬리는 페이저에 노출되고 윈도우 페이지 링크에도 실려서
        # 페이징 중에 활성 필터가 빠지지 않는다.
        assert resp.context["pager_query"] == "&status=planned"
        assert resp.context["page_obj"].paginator.count == 7
        # 쿼리스트링 꼬리의 &는 href 속성에서 자동 이스케이프된다
        # (올바른 HTML이며, 브라우저는 이동 시 다시 &로 디코딩한다).
        assert b"?page=2&amp;status=planned" in resp.content

    def test_나의_일정_상태_필터의_두번째_페이지는_일치하는_행만_보여준다(self, user_client, make_statuses):
        user, client = user_client()
        make_statuses(user, 7, status=UserEventStatus.Status.PLANNED)
        # 방문완료 행이 planned 필터 목록·건수에 섞여 들어가면 안 된다.
        make_statuses(user, 3, status=UserEventStatus.Status.VISITED)

        resp = client.get("/archive/statuses/?status=planned&page=2")

        page_obj = resp.context["page_obj"]
        assert page_obj.paginator.count == 7
        assert len(page_obj.object_list) == 2


@pytest.mark.django_db
class TestArchiveVisitsPagination:
    """방문 기록 (/archive/visits/) — 5건씩; 요약은 전체 기준을 유지한다."""

    def _make_visits(self, user, make_event, make_visit, count, with_memo=0):
        for i in range(count):
            event = make_event(title=f"Visited {i:02d}")
            make_visit(
                user,
                event=event,
                visited_on=f"2026-05-{(i % 27) + 1:02d}",
                short_review="좋았어요" if i < with_memo else "",
            )

    def test_다녀온_기록_첫_페이지는_다섯_건까지만_보여준다(self, user_client, make_event, make_visit):
        user, client = user_client()
        self._make_visits(user, make_event, make_visit, 7)

        resp = client.get("/archive/visits/")

        assert resp.status_code == 200
        page_obj = resp.context["page_obj"]
        assert page_obj.paginator.count == 7
        assert page_obj.paginator.num_pages == 2
        assert len(page_obj.object_list) == 5
        assert len(resp.context["visit_rows"]) == 5

    def test_다녀온_기록_두번째_페이지는_남은_건수를_보여준다(self, user_client, make_event, make_visit):
        user, client = user_client()
        self._make_visits(user, make_event, make_visit, 7)

        resp = client.get("/archive/visits/?page=2")

        assert len(resp.context["page_obj"].object_list) == 2

    def test_다녀온_기록_요약_카드는_페이지가_아닌_전체_건수를_보여준다(self, user_client, make_event, make_visit):
        user, client = user_client()
        self._make_visits(user, make_event, make_visit, 7, with_memo=3)

        resp = client.get("/archive/visits/")

        # 페이지에는 5행만 보이지만 요약 카드는 전체 7건 기준으로 집계한다.
        assert resp.context["total_count"] == 7
        assert resp.context["memo_count"] == 3
        assert len(resp.context["visit_rows"]) == 5
        assert resp.context["has_visits"] is True
