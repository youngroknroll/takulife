"""core/partials/_archive_nav.html — archive/{index,statuses,visits,items,
interests}.html이 공유하는 활동 하위 내비게이션 탭바 테스트.

현재 계약: 탭바는 전체 보기/나의 일정/다녀온 기록/직접 등록 네 콘텐츠 탭만
노출하고, "활동 달력"과 `/collection/` 링크는 절대 포함하지 않는다(Target IA
plan D1/§7-a-3, .docs/plans/2026-07-16-target-ia-plan.md). 찜은 2026-07-28
이후 모든 아카이브 페이지에서 `<nav aria-label="내 활동 하위 메뉴">` 바깥에
렌더링되므로 이 파일의 링크 수 검증은 4개이며, 찜 href가 nav 안에 없다는 사실만
확인한다 — 찜의 nav-바깥 배치 자체는
tests/archive/test_archive_interest_placement.py가 페이지별로 검증한다.

대표 페이지는 /archive/personal/(active="items")이다. 찜을 nav 안에 유지하는
페이지가 더는 없어 네 콘텐츠 페이지 중 어느 것을 골라도 동등하게 유효하기
때문이다. 탭바 계약이 여섯 링크에서 다섯, 다시 네 링크로 줄어든 변경 이력은
.docs/plans/2026-07-21-activity-editorial-plan.md,
.docs/plans/2026-07-23-activity-editorial-v2-plan.md,
.docs/plans/2026-07-23-activity-editorial-v3-plan.md를 참고.
"""
import pytest

pytestmark = pytest.mark.web


@pytest.mark.django_db
class TestArchiveNavTabs:
    def test_아카이브_내비게이션_탭바는_내_활동_계열_네_링크만_보여주고_찜과_활동_달력과_컬렉션_링크를_포함하지_않는다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/personal/")
        content = resp.content.decode()

        # 서브내비 랜드마크 범위로 한정한다 — 전역 헤더도 모든 페이지에서
        # /collection/을 링크하므로(D1), 페이지 전체를 검색하면 서브내비에
        # 여전히 그 링크가 있어도 통과해버린다.
        start = content.index('aria-label="내 활동 하위 메뉴"')
        end = content.index("</nav>", start)
        nav = content[start:end]

        assert nav.count("<a ") + nav.count('<a\n') + nav.count('<a\r\n') == 4
        assert '<span class="tab-label-full">나의 일정</span>' in nav
        assert '<span class="tab-label-full">다녀온 기록</span>' in nav
        assert '<span class="tab-label-full">직접 등록</span>' in nav
        # /archive/personal/은 active=="items"로 렌더링된다 — 직접 등록
        # 앵커 자체의 href+class를 한 문자열로 고정해 "어떤 탭이 활성인지"까지
        # 증명한다(단순히 어딘가 활성 탭이 있다는 사실만이 아니라).
        assert 'href="/archive/personal/" class="active">' in nav
        assert '<span class="tab-label-full">전체 보기</span>' in nav
        # 찜은 이제 어떤 페이지에서도 이 nav 자신의 링크가 아니다(모듈
        # docstring 참고) — 항상 `<nav>` 바깥에 렌더링되며 페이지별 검증은
        # tests/archive/test_archive_interest_placement.py의
        # TestIndexMovesInterestOutsideNavAfterSearch가 맡는다. href로
        # 고정한다: 하트 아이콘(♥) 도입으로 찜 앵커 내용이 바뀌어도 href는
        # 안정적 식별자다.
        assert 'href="/archive/interests/"' not in nav
        assert "nav-interest" not in nav
        # href로 고정한다: 라벨 클래스가 리네임돼도 href는 안정적 식별자다(위 찜 주석과 동일 관례).
        assert 'href="/archive/calendar/"' not in nav
        assert "/collection/" not in nav
