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
moves again, from /archive/visits/ to /archive/personal/, a stable sibling
that still keeps 찜 inside the nav (confirmed by
test_archive_interest_placement.py's TestSiblingPagesKeepInterestInsideNav),
so the 5-link count and the in-nav `href="/archive/interests/"` assertion
continue to hold. The tab-bar contract itself (five destinations, active
marking, no 활동 달력, no /collection/) is unchanged by this second swap —
only the active tab under test shifts from "다녀온 기록" to "직접 등록".
The 찜-outside-nav fact for /archive/visits/ is now covered by
tests/archive/test_archive_interest_placement.py's
TestIndexMovesInterestOutsideNavAfterSearch, so no coverage is lost.

2026-07-27 직접 등록 에디토리얼 통일: the representative-page chain above is
now exhausted — /archive/personal/ has also adopted the index-style
3-column toolbar (`hide_interest=True`), so every content list page
(record/statuses/visits/personal) now moves 찜 out of this nav. The only
remaining archive page that still renders 찜 *inside* `<nav aria-label="내
활동 하위 메뉴">` is /archive/interests/ itself (confirmed by
test_archive_interest_placement.py's TestSiblingPagesKeepInterestInsideNav,
which now carries only that one path). This test's representative page
therefore moves to /archive/interests/ — the last surviving sibling for the
찜-inside-nav 5-link fact, not a new one. That page's own include renders
with `active="interests"`, so the *active* element is no longer one of the
four content tabs (none of them carry `class="active"` there) — it is the
찜 anchor itself, which the nav partial marks via
`class="nav-interest active"` when `active == "interests"`. The active
assertion below is therefore rewritten to require `nav-interest active`
rather than a content tab's full-label span; the four content tabs' mere
*presence* (not their active state) and the 5-link count/no-활동 달력/no-
/collection/ facts are all unchanged by this swap. The 찜-outside-nav fact
for /archive/personal/ is now covered by
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

2026-07-28 찜 목록 페이지 자체의 통일 — CONTRACT REWRITE: the premise this
file's 2026-07-27 entry relied on — "/archive/interests/ is the last
surviving sibling that still renders 찜 *inside* this nav" — is now FALSE.
/archive/interests/ has adopted the same index-style 3-column toolbar
(`hide_interest=True`) as every other archive list page
(tests/archive/test_archive_interest_placement.py's 2026-07-28 entry), so
찜 is rendered outside `<nav aria-label="내 활동 하위 메뉴">` on *every*
reachable archive page. There is no longer any page for which a
"5-link, 찜-inside-nav" fact holds, so a representative-page swap cannot
repair this test the way five prior swaps did — the contract itself must
change.

The sub-nav's job is now exactly four content-tab destinations: 전체 보기
(record), 나의 일정 (statuses), 다녀온 기록 (visits), 직접 등록 (personal).
찜 is never one of this nav's own links on any page; it always lives outside
`<nav>`, next to the search form (asserted per-page by
tests/archive/test_archive_interest_placement.py's
TestIndexMovesInterestOutsideNavAfterSearch, which now covers all six list
pages including interests). This file's link-count assertion therefore drops
from five to four, and a new assertion locks that the 찜 anchor's href does
not appear inside the nav at all (replacing the old in-nav 찜-href/active-찜
assertions, which asserted the very fact that no longer holds anywhere).
What remains unchanged from the 2026-07-23 v2 §C contract this file has
carried since: the tab bar still excludes "활동 달력" and never links
`/collection/` — those two exclusions and the four content-tab labels'
presence are asserted exactly as before, just re-counted for four links
instead of five.

The representative page moves to /archive/personal/ (active="items",
i.e. 직접 등록), simply because it is the last page this file's
representative-page chain reached (2026-07-27 entry above) and remains a
valid, stable choice under the new four-link contract — any of the four
content pages would do equally well now that none of them keep 찜 inside
this nav.
"""
import pytest

pytestmark = pytest.mark.web


@pytest.mark.django_db
class TestArchiveNavTabs:
    def test_아카이브_내비게이션_탭바는_내_활동_계열_네_링크만_보여주고_찜과_활동_달력과_컬렉션_링크를_포함하지_않는다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/personal/")
        content = resp.content.decode()

        # Scoped to the sub-nav landmark itself — the global header also
        # links to /collection/ on every page now (D1), so a page-wide
        # search for "/collection/" would pass even if the sub-nav still
        # carried it.
        start = content.index('aria-label="내 활동 하위 메뉴"')
        end = content.index("</nav>", start)
        nav = content[start:end]

        assert nav.count("<a ") + nav.count('<a\n') + nav.count('<a\r\n') == 4
        assert '<span class="tab-label-full">나의 일정</span>' in nav
        assert '<span class="tab-label-full">다녀온 기록</span>' in nav
        assert '<span class="tab-label-full">직접 등록</span>' in nav
        # /archive/personal/ renders with active=="items" — anchored to the
        # 직접 등록 anchor's own href+class in one substring so the check
        # proves *which* tab is marked active, not merely that some tab
        # somewhere is.
        assert 'href="/archive/personal/" class="active">' in nav
        assert '<span class="tab-label-full">전체 보기</span>' in nav
        # 찜 is never one of this nav's own links on any page now (모듈
        # docstring 2026-07-28 참고) — it always renders outside `<nav>`,
        # verified per-page by
        # tests/archive/test_archive_interest_placement.py's
        # TestIndexMovesInterestOutsideNavAfterSearch. href로 고정한다: 하트
        # 아이콘(♥) 도입으로 찜 앵커 내용이 바뀌어도 href는 안정적 식별자다.
        assert 'href="/archive/interests/"' not in nav
        assert "nav-interest" not in nav
        # href로 고정한다: 라벨 클래스가 리네임돼도 href는 안정적 식별자다(위 찜 주석과 동일 관례).
        assert 'href="/archive/calendar/"' not in nav
        assert "/collection/" not in nav
