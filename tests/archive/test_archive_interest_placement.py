"""_archive_nav.html의 찜 링크 배치 계약 — 2026-07-23 §H(플랜:
.docs/plans/2026-07-23-activity-editorial-v3-plan.md) 대상 회귀.

§H는 /archive/(index.html)에서만 찜 앵커를 <nav aria-label="내 활동 하위
메뉴"> 바깥, .archive-search 폼 뒤로 옮긴다. 구현은 부정 플래그
`{% if not hide_interest %}`로 진행되며, index.html의 include에만
hide_interest=True를 전달하고 나머지 7개 템플릿(statuses/visits/
personal_entries/interests/calendar/visit_create/visit_edit)은 무수정으로
남는다 — 즉 플래그를 넘기지 않으면 기존처럼 nav 안에 찜이 남아야 한다.

플랜이 명시한 리스크: 기본값이 실수로 뒤집히면(예: `if hide_interest`로
반전되거나 기본값이 True로 바뀌면) 나머지 7개 페이지에서 찜 진입로가 통째로
사라지는데, 종전 test_archive_nav.py는 /archive/statuses/ 1페이지만
실측했기 때문에 이 회귀를 잡지 못했다(그 파일의 "다른 페이지는 include
방식이 동일해 반복 검증하지 않는다"는 전제가 이번 변경으로 깨짐 — 해당
파일 상단 docstring도 갱신됨). 이 파일이 그 커버리지 갭을 메운다.

visit_create.html/visit_edit.html은 폼 제출 흐름(POST 대상, VisitRecord
픽스처 준비)이 목적이라 이 마크업 배치 계약과는 비용 대비 가치가 낮다고
판단해 파라미터화 대상에서 제외한다 — 두 템플릿도 동일한 include 호출이라
정적 검사(§H 실측)로 이미 무수정임이 확인되었고, 런타임 렌더 확인은 각각의
전용 뷰 테스트(test_archive_visit_create_view.py,
test_archive_visit_edit_view.py)가 더 적합한 위치다.
"""
import pytest

pytestmark = pytest.mark.web


def _extract_nav(content):
    start = content.index('aria-label="내 활동 하위 메뉴"')
    end = content.index("</nav>", start)
    return content[start:end]


@pytest.mark.django_db
class TestSiblingPagesKeepInterestInsideNav:
    @pytest.mark.parametrize(
        "path",
        [
            "/archive/statuses/",
            "/archive/visits/",
            "/archive/items/",
            "/archive/interests/",
            "/archive/calendar/",
        ],
    )
    def test_index_외_아카이브_페이지에서_찜_링크는_서브내비게이션_안에_그대로_남는다(
        self, user_client, path
    ):
        _, client = user_client()

        resp = client.get(path)
        content = resp.content.decode()

        nav = _extract_nav(content)

        # href로 고정한다: 하트 아이콘(♥) 도입으로 앵커 내용이
        # `<span aria-hidden="true">♥</span> 찜 목록</a>`가 되어 레이블 문자열
        # `>찜 목록</a>`(꺾쇠 직후 바로 찜)로는 더 이상 매치되지 않는다.
        # href는 아이콘·레이블 문구 변경에 영향받지 않는 안정적 식별자다.
        assert 'href="/archive/interests/"' in nav


@pytest.mark.django_db
class TestIndexMovesInterestOutsideNavAfterSearch:
    def test_아카이브_전체보기_페이지에서_찜_링크는_내비게이션_밖_검색폼_뒤로_이동한다(
        self, user_client
    ):
        _, client = user_client()

        resp = client.get("/archive/")
        content = resp.content.decode()

        nav = _extract_nav(content)
        # (a) nav 범위 안에는 찜이 없다.
        # href로 고정한다: 하트 아이콘(♥) 도입으로 앵커 내용이
        # `<span aria-hidden="true">♥</span> 찜 목록</a>`가 되어 레이블 문자열
        # `>찜 목록</a>`로는 더 이상 매치되지 않는다. href는 아이콘·레이블
        # 문구 변경에 영향받지 않는 안정적 식별자다.
        assert 'href="/archive/interests/"' not in nav

        # (b) 페이지 전체에는 찜 링크가 존재한다(사라진 게 아니라 옮겨진 것).
        assert 'href="/archive/interests/"' in content

        # (c) DOM 순서상 검색 폼이 찜 앵커보다 앞에 온다.
        search_index = content.index('class="archive-search"')
        interest_index = content.index('href="/archive/interests/"')
        assert search_index < interest_index

        # (d) 접근성 계약: 찜 앵커의 하트 아이콘은 aria-hidden으로 감싸져
        # 스크린리더에는 "찜 목록" 텍스트 레이블만 노출되어야 한다.
        interest_anchor_end = content.index("</a>", interest_index)
        interest_anchor = content[interest_index:interest_anchor_end]
        assert '<span aria-hidden="true">' in interest_anchor
