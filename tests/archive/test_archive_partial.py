"""네 아카이브 목록 페이지의 ?partial=1 조각 분기 테스트.

검증 대상: ?partial=1은 전체 HTML 문서가 아니라 결과 조각(목록+빈 상태+페이저)만
반환하며 라이브 검색 JS가 이를 #archive-results에 교체한다. base.html은
템플릿 체인에 없고, 일반 요청은 전체 페이지를 그대로 렌더링하며,
@login_required 게이트는 partial 분기에도 그대로 적용되어 비로그인
?partial=1 요청은 로그인으로 리다이렉트될 뿐 조각을 노출하지 않는다.
partial 분기는 전체 페이지와 같은 q 필터를 적용하며, "1"이 아닌 partial
값은 전체 페이지로 대체 응답한다.
"""
import pytest
from django.test import Client

from archive.models import PersonalEntry

pytestmark = pytest.mark.web

# 검색이 붙은 각 아카이브 페이지별 (url, full_template, fragment_template).
ARCHIVE_PAGES = [
    ("/archive/", "core/archive/index.html", "core/partials/_archive_results_record.html"),
    ("/archive/statuses/", "core/archive/statuses.html", "core/partials/_archive_results_statuses.html"),
    ("/archive/visits/", "core/archive/visits.html", "core/partials/_archive_results_visits.html"),
    ("/archive/personal/", "core/archive/personal_entries.html", "core/partials/_archive_results_personal.html"),
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
        # 조각은 전체 페이지 크롬을 끌고 들어오면 안 된다.
        assert full_template not in names
        assert "base.html" not in names
        # 문서 셸도 없고 swap 래퍼도 없다(그건 전체 페이지에만 있다).
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
        # 전체 페이지는 swap 대상 안에 조각을 감싸 include한다.
        assert fragment_template in names
        assert b'id="archive-results"' in resp.content
        assert b"<html" in resp.content.lower()

    @pytest.mark.parametrize(
        "url,full_template,fragment_template", ARCHIVE_PAGES, ids=ARCHIVE_PAGE_IDS
    )
    def test_비로그인_사용자의_partial_요청은_로그인_페이지로_리다이렉트된다(self, url, full_template, fragment_template):
        client = Client()  # 비로그인

        resp = client.get(url + "?partial=1")

        # @login_required는 partial 분기에도 그대로 적용된다.
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
        # /archive/ 대시보드는 statuses와 _archive_status_context를 공유하지만
        # record 조각은 다른 페이지 크기로 렌더링하므로 직접 검증한다.
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
        # has_any=True, 활성 status 필터가 0건 매칭, 검색어 없음 → record
        # 조각의 `elif has_any` 안내 분기(검색-빈 분기가 아니라)를 검증한다.
        user, client = user_client()
        planned = make_event(title="예정 행사")
        make_status(user, event=planned, status="planned")

        resp = client.get("/archive/?status=missed&partial=1")

        assert resp.status_code == 200
        assert resp.context["has_any"] is True
        assert resp.context["has_statuses"] is False
        assert "예정 행사".encode() not in resp.content
        assert "이 상태로 저장한 이벤트가 없습니다".encode() in resp.content

    def test_나의_일정_partial_렌더링이_페이지를_넘으면_partial_없는_페이저_링크를_포함한다(self, user_client, make_event, make_status):
        # 한 페이지보다 레코드가 많음 → 페이저는 조각 안에 렌더링돼야 하고,
        # 그 링크는 partial=을 절대 실으면 안 된다(그러면 클릭 시 크롬 없는
        # 조각으로 이동해버린다). /archive/statuses/는 5건씩 페이지네이션된다.
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
        # 렌더된 조각에도 필터 결과가 그대로 반영된다.
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

        resp = client.get("/archive/personal/?q=매칭&partial=1")

        assert resp.status_code == 200
        assert "매칭 카페".encode() in resp.content
        assert "제외 장소".encode() not in resp.content

    def test_직접_등록_목록에서_굿즈_항목은_찜_상태_승격_액션은_없고_삭제만_가능하다(self, user_client, make_entry):
        # GOODS는 더 이상 찜/상태/승격 대상이 아니다(collection domain
        # plan §3-3, gate M1: C2 머지 후 굿즈는 모든 UI 경로에서 접근 불가) —
        # 굿즈 행은 찜/상태 버튼과 공식 제보 폼 없이 렌더링돼야 하고
        # 장소 행은 그대로 유지한다.
        user, client = user_client()
        make_entry(user, kind=PersonalEntry.Kind.PLACE, title="장소 항목")
        make_entry(user, kind="goods", title="굿즈 항목")

        resp = client.get("/archive/personal/")

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
        # 삭제는 plan이 제한하는 대상이 아니다(상태/방문/찜/승격만 제한) —
        # CollectionItem으로 이관되기 전(C4) 과도기 동안 굿즈 행도 스스로
        # 삭제할 수단은 남아 있어야 한다.
        assert f'data-delete-entry-id="{goods_id}"'.encode() in content
