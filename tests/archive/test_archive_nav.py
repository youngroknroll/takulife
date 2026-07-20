"""core/partials/_archive_nav.html — the Activity sub-nav shared across
archive/{index,statuses,visits,items,interests}.html.

2026-07-21 리디자인 ④단계 §B (.docs/plans/2026-07-21-activity-editorial-plan.md):
the former <details> accordion was replaced by an always-visible tab bar
(user-confirmed "시안 우선"); that accordion/summary/panel markup was a
disposable implementation detail and is not protected here. What the original
test locked in — and what this file keeps locking in across the markup swap —
is the underlying navigation contract from Target IA plan D1/§7-a-3
(.docs/plans/2026-07-16-target-ia-plan.md): the sub-nav exposes only the
Activity-family destinations (record/statuses/visits/calendar/items +
interests), the active destination is marked, and it carries no /collection/
link anywhere (collection moved to a top-level destination;
tests/archive/test_archive_collection_view.py's TestArchiveCollectionNav
locks that /collection/ itself doesn't link back into this sub-nav).
Exercised via /archive/statuses/ as one representative page — the partial's
inclusion is otherwise identical across the other archive pages (same
include tag, only `active`/`active_label` vary), so this file does not
re-assert the same structural fact once per page.
"""
import pytest

pytestmark = pytest.mark.web


@pytest.mark.django_db
class TestArchiveNavTabs:
    def test_아카이브_내비게이션_탭바는_내_활동_계열_다섯_링크와_찜_목록만_보여주고_컬렉션_링크를_포함하지_않는다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/statuses/")
        content = resp.content.decode()

        # Scoped to the sub-nav landmark itself — the global header also
        # links to /collection/ on every page now (D1), so a page-wide
        # search for "/collection/" would pass even if the sub-nav still
        # carried it.
        start = content.index('aria-label="내 활동 하위 메뉴"')
        end = content.index("</nav>", start)
        nav = content[start:end]

        assert nav.count("<a ") + nav.count('<a\n') + nav.count('<a\r\n') == 6
        assert '>나의 일정</a>' in nav
        assert 'class="active">나의 일정</a>' in nav
        assert ">다녀온 기록</a>" in nav
        assert ">활동 달력</a>" in nav
        assert ">직접 등록</a>" in nav
        assert ">전체 보기</a>" in nav
        assert ">찜 목록</a>" in nav
        assert "/collection/" not in nav
