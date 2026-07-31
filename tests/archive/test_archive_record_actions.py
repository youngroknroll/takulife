"""SSR 페이지에서 내 아카이브 기록 액션 연결을 검증하는 테스트.

검증 대상:
- 기록장 (/archive/)에는 정리 체크리스트가 없고, 기록 추가 링크가 실제로
  동작하며, 방문 완료 행에만 행별 기록 바로가기가 보인다.
- 방문 기록 (/archive/visits/)에는 더 이상 기록 안내 패널이 없다 — 그 안내는
  이제 작성 페이지(/archive/visits/new/)에 있다.
"""
import pytest

from archive.models import UserEventStatus

pytestmark = pytest.mark.web


@pytest.mark.django_db
class TestArchiveRecordPageActions:
    def test_기록장_페이지에는_정리_체크리스트가_없다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/")

        assert "정리 체크리스트" not in resp.content.decode()

    def test_기록장_페이지에서_기록_추가_버튼은_준비중이_아니라_실제_링크로_동작한다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/")

        # "(준비 중)" 비활성 버튼은 사라지고 작성 페이지로 가는 실제 링크가 들어왔다.
        body = resp.content.decode()
        assert "준비 중" not in body
        assert 'href="/archive/visits/new/"' in body

    def test_방문_완료_행은_기록_바로가기_링크를_보여준다(self, user_client, make_event, make_status):
        user, client = user_client()
        event = make_event(title="다녀온 행사")
        make_status(user, event=event, status=UserEventStatus.Status.VISITED)

        resp = client.get("/archive/")

        assert f"/archive/visits/new/?subject=event:{event.id}".encode() in resp.content

    def test_방문_예정_행은_기록_바로가기_링크를_보여주지_않는다(self, user_client, make_event, make_status):
        user, client = user_client()
        event = make_event(title="갈 예정 행사")
        make_status(user, event=event, status=UserEventStatus.Status.PLANNED)

        resp = client.get("/archive/")

        # 행별 기록 바로가기는 ?subject=를 갖지만 일반 기록 추가 링크는 갖지 않는다.
        assert b"/archive/visits/new/?subject=" not in resp.content


@pytest.mark.django_db
class TestVisitRecordCollectionShortcut:
    """다녀온 기록 (/archive/visits/) 카드에 굿즈 등록 바로가기가 붙는다
    (collection domain design plan §4 PR-C5b-2 CP-V1). 기존 수정/기록 삭제
    액션 옆에 ?visit_record=<id>로 컬렉션 등록 폼을 프리셀렉트하는 링크가
    붙는다 — test_방문_완료_행은_기록_바로가기_링크를_보여준다의 미러."""

    def test_다녀온_기록_카드는_컬렉션_등록_바로가기_링크를_보여준다(self, user_client, make_event, make_visit):
        user, client = user_client()
        event = make_event(title="다녀온 행사")
        record = make_visit(user, event=event, visited_on="2026-05-01")

        resp = client.get("/archive/visits/")

        assert f"/collection/new/?visit_record={record.id}".encode() in resp.content


@pytest.mark.django_db
class TestVisitGuidanceMoved:
    def test_다녀온_기록_페이지에는_기록_안내_패널이_없다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/visits/")

        assert "기록 안내" not in resp.content.decode()

    def test_기록_작성_페이지에는_기록_안내_패널이_있다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/visits/new/")

        assert "기록 안내" in resp.content.decode()
