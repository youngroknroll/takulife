"""core/partials/_archive_nav.html — the Activity sub-nav accordion shared
across archive/{index,statuses,visits,items,interests}.html.

Target IA plan D1/§7-a-3 (.docs/plans/2026-07-16-target-ia-plan.md): the
collection group was removed from the accordion (collection moved to a
top-level destination, tests/archive/test_archive_collection_view.py's
TestArchiveCollectionNav locks that it's gone from /collection/ itself) — 2
groups remain (내 기록·직접 등록), the collapsed header reads "내 활동 ·
{label}" (was "내 아카이브"), and the accordion carries no /collection/ link
anywhere. Exercised via /archive/statuses/ as one representative page — the
partial's inclusion is otherwise identical across the other archive pages
(same include tag, only `active`/`active_label` vary), so this file does not
re-assert the same structural fact once per page.
"""
import pytest

pytestmark = pytest.mark.web


@pytest.mark.django_db
class TestArchiveNavAccordion:
    def test_아카이브_내비게이션_아코디언은_내_활동_라벨의_두_그룹만_보여주고_컬렉션_링크를_포함하지_않는다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/statuses/")
        content = resp.content.decode()

        assert "내 활동 · 나의 일정" in content

        # Scoped to the accordion panel itself — the global header also links
        # to /collection/ on every page now (D1), so a page-wide search for
        # "/collection/" would pass even if the accordion still carried it.
        start = content.index('class="archive-nav-panel"')
        end = content.index("</details>", start)
        panel = content[start:end]

        assert panel.count('class="archive-nav-group"') == 2
        assert "/collection/" not in panel
