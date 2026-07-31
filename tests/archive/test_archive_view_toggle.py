"""/archive/와 /archive/calendar/의 목록 | 달력 뷰 토글 테스트.

2026-07-23 v2 계획 §C(.docs/plans/2026-07-23-activity-editorial-v2-plan.md):
"활동 달력" 탭이 두 페이지를 잇는 같은 라우트 계열 뷰 토글로 바뀐다. 컬렉션 뷰
토글(필터를 보존하는 같은 라우트 쿼리 전환)과 달리 이 토글은 status/q를 읽지
않는 페이지로 라우트를 넘나들므로(templates/core/archive/calendar.html:31-58,70-73)
`달력` href에 죽은 쿼리 문자열이 실려선 안 된다. 왕복 양방향을 모두 검증한다.

2026-07-27 내 활동 셸 폴리시 v2(.docs/plans/2026-07-27-activity-shell-v2-plan.md):
같은 토글이 /archive/statuses/, /archive/visits/에도 확장된다. 아래 테스트는
검증 범위를 `.activity-view-toggle` 블록 자체로 좁힌다 — 페이지의 다른 위치에
있는 필터 "전체" 칩이 쿼리 없는 같은 href를 렌더할 수 있어, 범위를 좁히지 않으면
토글이 없어도 검사가 통과해버린다.
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
