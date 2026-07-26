"""core/partials/_archive_nav.html — the Activity sub-nav shared across
archive/{index,statuses,visits,items,interests}.html.

2026-07-21 리디자인 ④단계 §B (.docs/plans/2026-07-21-activity-editorial-plan.md):
the former <details> accordion was replaced by an always-visible tab bar
(user-confirmed "시안 우선"); that accordion/summary/panel markup was a
disposable implementation detail and is not protected here.

2026-07-23 v2 §C (.docs/plans/2026-07-23-activity-editorial-v2-plan.md):
the user explicitly confirmed dropping "활동 달력" from this tab bar in
favor of a 목록/달력 view toggle on /archive/ and /archive/calendar/
themselves (사용자 확정 #3 — overriding all three reviewers' recommendation
to keep the tab). The sub-nav link count contract therefore moves from six
to five; "활동 달력" is no longer one of the tab bar's own links (it stays
reachable via the new toggle and the site footer, per the plan's stated
residual-risk note). What remains locked in here — unchanged by this
count shrink — is the underlying navigation contract from Target IA plan
D1/§7-a-3 (.docs/plans/2026-07-16-target-ia-plan.md): the sub-nav exposes
only the remaining Activity-family destinations (record/statuses/visits/
items + interests), the active destination is marked, and it carries no
/collection/ link anywhere (collection moved to a top-level destination;
tests/archive/test_archive_collection_view.py's TestArchiveCollectionNav
locks that /collection/ itself doesn't link back into this sub-nav).
Exercised via /archive/statuses/ as one representative page — the partial's
inclusion is otherwise identical across the other archive pages (same
include tag, only `active`/`active_label` vary), so this file does not
re-assert the same structural fact once per page.

2026-07-23 v3 §H (.docs/plans/2026-07-23-activity-editorial-v3-plan.md):
that "otherwise identical across pages" premise above is now broken for one
page. /archive/(index.html) alone moves the 찜 anchor out of this nav (via a
`hide_interest` include flag) while the other seven pages keep it inside —
so /archive/statuses/ no longer stands in for /archive/ on the
찜-inside-nav fact. This file is left unchanged (statuses.html itself is
unmodified and this test's 5-link/no-찜-leak assertions still hold there),
but the cross-page coverage gap this premise created is now closed by
tests/archive/test_archive_interest_placement.py, which asserts the
sibling-pages-keep-찜-inside-nav fact across all five reachable list pages
and the index-specific moved-outside-nav fact separately.

2026-07-24 나의 일정 에디토리얼 통일: the §H claim above that
"statuses.html itself is unmodified and this test's 5-link/no-찜-leak
assertions still hold there" is now FALSE — /archive/statuses/ has adopted
the index-style 3-column toolbar (`hide_interest=True`), moving its 찜
anchor out of this nav just like /archive/ and /archive/calendar/. This
test's representative page therefore moves from /archive/statuses/ to
/archive/visits/, a stable sibling that still keeps 찜 inside the nav, so
the 5-link count and the in-nav `href="/archive/interests/"` assertion
continue to hold. The tab-bar contract itself (five destinations, active
marking, no 활동 달력, no /collection/) is unchanged by this swap — only
the active tab under test shifts from "나의 일정" to "다녀온 기록". The
찜-outside-nav fact for /archive/statuses/ is now covered by
tests/archive/test_archive_interest_placement.py's
TestIndexMovesInterestOutsideNavAfterSearch, so no coverage is lost.

2026-07-27 다녀온 기록 에디토리얼 통일: /archive/visits/ has now also
adopted the index-style 3-column toolbar (`hide_interest=True`), moving its
찜 anchor out of this nav — so it can no longer stand in for the
찜-inside-nav 5-link fact either. This test's representative page therefore
moves again, from /archive/visits/ to /archive/items/, a stable sibling
that still keeps 찜 inside the nav (confirmed by
test_archive_interest_placement.py's TestSiblingPagesKeepInterestInsideNav),
so the 5-link count and the in-nav `href="/archive/interests/"` assertion
continue to hold. The tab-bar contract itself (five destinations, active
marking, no 활동 달력, no /collection/) is unchanged by this second swap —
only the active tab under test shifts from "다녀온 기록" to "직접 등록".
The 찜-outside-nav fact for /archive/visits/ is now covered by
tests/archive/test_archive_interest_placement.py's
TestIndexMovesInterestOutsideNavAfterSearch, so no coverage is lost.

2026-07-27 내 활동 셸 폴리시 v2: each tab's label text moved from a bare
text node into a pair of spans — `<span class="tab-label-full">LABEL</span>`
followed by `<span class="tab-label-short">SHORT</span>` — so a narrow
viewport can show the short form via CSS while the full label stays in the
accessibility tree. A bare `>LABEL</a>` substring check no longer matches
(the label is no longer the last thing before `</a>`; the short span is), so
assertions below match the full-label span instead. The active tab is
asserted by anchoring `class="active"` directly to the active tab's
full-label span in one substring, so the check still proves *which* tab is
marked active, not merely that some tab somewhere is.
"""
import pytest

pytestmark = pytest.mark.web


@pytest.mark.django_db
class TestArchiveNavTabs:
    def test_아카이브_내비게이션_탭바는_내_활동_계열_다섯_링크만_보여주고_활동_달력과_컬렉션_링크를_포함하지_않는다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/items/")
        content = resp.content.decode()

        # Scoped to the sub-nav landmark itself — the global header also
        # links to /collection/ on every page now (D1), so a page-wide
        # search for "/collection/" would pass even if the sub-nav still
        # carried it.
        start = content.index('aria-label="내 활동 하위 메뉴"')
        end = content.index("</nav>", start)
        nav = content[start:end]

        assert nav.count("<a ") + nav.count('<a\n') + nav.count('<a\r\n') == 5
        assert '<span class="tab-label-full">나의 일정</span>' in nav
        assert (
            'class="active"><span class="tab-label-full">직접 등록</span>'
            in nav
        )
        assert '<span class="tab-label-full">다녀온 기록</span>' in nav
        assert '<span class="tab-label-full">직접 등록</span>' in nav
        assert '<span class="tab-label-full">전체 보기</span>' in nav
        # href로 고정한다: 하트 아이콘(♥) 도입으로 찜 앵커 내용이
        # `<span aria-hidden="true">♥</span> 찜 목록</a>`가 되면 레이블 문자열
        # `>찜 목록</a>`로는 매치되지 않는다. href는 아이콘·레이블 문구
        # 변경에 영향받지 않는 안정적 식별자다.
        assert 'href="/archive/interests/"' in nav
        assert '<span class="tab-label-full">활동 달력</span>' not in nav
        assert "/collection/" not in nav
