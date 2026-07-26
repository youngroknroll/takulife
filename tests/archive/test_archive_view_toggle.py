"""목록 | 달력 view toggle on /archive/ and /archive/calendar/.

2026-07-23 v2 plan §C (.docs/plans/2026-07-23-activity-editorial-v2-plan.md,
사용자 확정 #3): the "활동 달력" sub-nav tab is replaced by a same-route-family
view toggle on the two pages it connects. Unlike the collection view toggle
(a same-route query-param switch that preserves filters), this toggle crosses
routes to a page that reads neither `status` nor `q`
(templates/core/archive/calendar.html:31-58,70-73) — so its `달력` href must
never carry a dead query string. Both directions of the round trip are
covered so a regression on either page is caught.

2026-07-27 내 활동 셸 폴리시 v2 (.docs/plans/2026-07-27-activity-shell-v2-plan.md):
the same 목록/달력 toggle is extended to /archive/statuses/ and
/archive/visits/, both of which have an honest current URL to mark
aria-current on (unlike the plain-tab-bar days). The new tests below scope
their assertions to the `.activity-view-toggle` block itself — on both pages
a status/filter "전체" chip elsewhere on the page can render a plain
`href="/archive/statuses/"` or `href="/archive/visits/"` with no query
string when the page has no active search/filter, which would make an
unscoped substring check pass even without the toggle existing.
"""
import pytest

pytestmark = pytest.mark.web


@pytest.mark.django_db
class TestArchiveViewToggle:
    def test_전체_보기에_목록_달력_토글이_렌더되고_달력_링크는_쿼리_파라미터가_없다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/?status=planned&q=매칭")

        content = resp.content.decode()
        assert 'href="/archive/calendar/"' in content
        assert ">달력<" in content
        assert ">목록<" in content

    def test_전체_보기에서_현재_뷰인_목록_링크에_aria_current가_붙는다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/")

        content = resp.content.decode()
        start = content.index(">목록<")
        preceding = content[max(0, start - 200):start]
        assert 'aria-current="page"' in preceding

    def test_활동_달력에_목록_달력_토글이_렌더되고_현재_뷰인_달력_링크에_aria_current가_붙는다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/calendar/")

        content = resp.content.decode()
        assert 'href="/archive/"' in content
        assert ">목록<" in content

        start = content.index(">달력<")
        preceding = content[max(0, start - 200):start]
        assert 'aria-current="page"' in preceding

    def test_나의_일정에_목록_달력_토글이_렌더되고_현재_뷰인_목록_링크에_aria_current가_붙는다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/statuses/")

        content = resp.content.decode()
        start = content.index('class="activity-view-toggle"')
        end = content.index("</div>", start)
        toggle = content[start:end]

        assert 'href="/archive/statuses/"' in toggle
        assert 'aria-current="page"' in toggle
        assert 'href="/archive/calendar/"' in toggle
        assert ">목록<" in toggle
        assert ">달력<" in toggle

    def test_다녀온_기록에_목록_달력_토글이_렌더되고_현재_뷰인_목록_링크에_aria_current가_붙는다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/visits/")

        content = resp.content.decode()
        start = content.index('class="activity-view-toggle"')
        end = content.index("</div>", start)
        toggle = content[start:end]

        assert 'href="/archive/visits/"' in toggle
        assert 'aria-current="page"' in toggle
        assert 'href="/archive/calendar/"' in toggle
        assert ">목록<" in toggle
        assert ">달력<" in toggle
