"""목록 | 달력 view toggle on /archive/ and /archive/calendar/.

2026-07-23 v2 plan §C (.docs/plans/2026-07-23-activity-editorial-v2-plan.md,
사용자 확정 #3): the "활동 달력" sub-nav tab is replaced by a same-route-family
view toggle on the two pages it connects. Unlike the collection view toggle
(a same-route query-param switch that preserves filters), this toggle crosses
routes to a page that reads neither `status` nor `q`
(templates/core/archive/calendar.html:31-58,70-73) — so its `달력` href must
never carry a dead query string. Both directions of the round trip are
covered so a regression on either page is caught.
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
