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

**2026-07-24 일반화** (활동 달력 에디토리얼 계획 §8-A D7 / §8-A-1 item 2 /
§8-A-2): 활동 달력이 서브탭 행을 목록과 완전 통일하면서(R-1) 찜도 index와
같은 3구획 grid 배치를 채택 — `<nav>` 밖으로 옮기고 `hide_interest=True`를
전달하게 됐다. 이는 가드가 "확장점"으로 이미 문서화한 구조적 이유의 두
번째 적용(§8-A-1 WED 판정)이지 우회가 아니므로, `/archive/calendar/`를
`TestSiblingPagesKeepInterestInsideNav`(nav 안 유지 그룹)에서 제거하고
`TestIndexMovesInterestOutsideNavAfterSearch`(nav 밖 이동 그룹)로 옮긴다 —
커버리지 삭제가 아니라 이동이다. 검색 필드 DOM-순서 마커는 index가
`.archive-search`(공유 파셜), 달력이 `.calendar-search`(로컬 마크업, WED
사전 명세 §8-A-1 item 1 조건)로 클래스명이 달라 페이지별로 다른 마커를
쓰도록 파라미터화했다.

**2026-07-24 나의 일정 에디토리얼 통일**: `/archive/statuses/`도 index와
동일한 3구획 툴바를 채택해(`hide_interest=True` 전달, 찜 앵커가 검색 폼
뒤로 이동) 위와 동일한 구조적 이유(§8-A-1 WED 판정 확장점)의 세 번째
적용이 됐다. `/archive/statuses/`를 `TestSiblingPagesKeepInterestInsideNav`
에서 제거하고 `TestIndexMovesInterestOutsideNavAfterSearch`로 옮긴다 —
이번에도 삭제가 아니라 이동이다. statuses는 달력과 달리 로컬 검색 마크업이
아니라 공유 파셜 `_archive_search.html`을 그대로 쓰므로, 검색 마커는 달력의
`.calendar-search`가 아니라 index와 동일한 `.archive-search`다.
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
            "/archive/visits/",
            "/archive/items/",
            "/archive/interests/",
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
    @pytest.mark.parametrize(
        ("path", "search_marker"),
        [
            ("/archive/", 'class="archive-search"'),
            ("/archive/statuses/", 'class="archive-search"'),
            ("/archive/calendar/", 'class="calendar-search"'),
        ],
        ids=["index", "statuses", "calendar"],
    )
    def test_아카이브_전체보기_페이지에서_찜_링크는_내비게이션_밖_검색폼_뒤로_이동한다(
        self, user_client, path, search_marker
    ):
        _, client = user_client()

        resp = client.get(path)
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

        # (c) DOM 순서상 검색 폼이 찜 앵커보다 앞에 온다. 마커 클래스는
        # 페이지마다 다르다 — index는 공유 파셜 `.archive-search`,
        # 달력은 로컬 마크업 `.calendar-search`(모듈 docstring 2026-07-24
        # 일반화 참고).
        search_index = content.index(search_marker)
        interest_index = content.index('href="/archive/interests/"')
        assert search_index < interest_index

        # (d) 접근성 계약: 찜 앵커의 하트 아이콘은 aria-hidden으로 감싸져
        # 스크린리더에는 "찜 목록" 텍스트 레이블만 노출되어야 한다.
        interest_anchor_end = content.index("</a>", interest_index)
        interest_anchor = content[interest_index:interest_anchor_end]
        assert '<span aria-hidden="true">' in interest_anchor
