"""SSR 페이지에서 내 아카이브 기록 액션 연결을 검증하는 테스트.

검증 대상:
- 기록장 (/archive/)에는 정리 체크리스트가 없고, 기록 추가 링크가 실제로
  동작하며, 방문 완료 행에만 행별 기록 바로가기가 보인다.
- 방문 기록 (/archive/visits/)에는 더 이상 기록 안내 패널이 없다 — 그 안내는
  이제 작성 페이지(/archive/visits/new/)에 있다.
"""

import html
import re

import pytest

from archive.models import PersonalEntry, UserEventStatus, VisitRecord
from events.models import Event

pytestmark = pytest.mark.web


@pytest.mark.django_db
class TestArchiveRecordPageActions:
    def test_기록장_페이지에는_정리_체크리스트가_없다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/")

        assert "정리 체크리스트" not in resp.content.decode()

    def test_기록장_페이지에서_기록_추가_버튼은_준비중이_아니라_실제_링크로_동작한다(
        self, user_client
    ):
        _, client = user_client()

        resp = client.get("/archive/")

        # "(준비 중)" 비활성 버튼은 사라지고 작성 페이지로 가는 실제 링크가 들어왔다.
        body = resp.content.decode()
        assert "준비 중" not in body
        assert 'href="/archive/visits/new/"' in body

    def test_방문_완료_행은_기록_바로가기_링크를_보여준다(
        self, user_client, make_event, make_status
    ):
        user, client = user_client()
        event = make_event(title="다녀온 행사")
        make_status(user, event=event, status=UserEventStatus.Status.VISITED)

        resp = client.get("/archive/")

        assert f"/archive/visits/new/?subject=event:{event.id}".encode() in resp.content

    def test_방문_예정_행은_기록_바로가기_링크를_보여주지_않는다(
        self, user_client, make_event, make_status
    ):
        user, client = user_client()
        event = make_event(title="갈 예정 행사")
        make_status(user, event=event, status=UserEventStatus.Status.PLANNED)

        resp = client.get("/archive/")

        # 행별 기록 바로가기는 ?subject=를 갖지만 일반 기록 추가 링크는 갖지 않는다.
        assert b"/archive/visits/new/?subject=" not in resp.content


def _hrefs(resp):
    return [html.unescape(href) for href in re.findall(r'href="([^"]*)"', resp.content.decode())]


def _official_event_subject(user):
    event = Event.objects.create(
        pk=920_001, title="공식 행사", publish_status=Event.PublishStatus.PUBLISHED
    )
    return {"event": event}


def _personal_place_subject(user):
    entry = PersonalEntry.objects.create(
        pk=920_001, user=user, kind=PersonalEntry.Kind.PLACE, title="직접 등록 장소"
    )
    return {"personal_entry": entry}


_NO_MEMO = [("2026-06-01", "")]
_OLD_MEMO_THEN_NEW_NO_MEMO = [("2026-05-01", "좋았다"), ("2026-06-01", "")]
_WITH_MEMO = [("2026-06-01", "좋았다")]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("path", "build_subject", "records"),
    [
        pytest.param(
            "/archive/", _official_event_subject, _NO_MEMO, id="기록장_공식_행사_메모_없음"
        ),
        pytest.param(
            "/archive/statuses/",
            _official_event_subject,
            _NO_MEMO,
            id="상태_목록_공식_행사_메모_없음",
        ),
        pytest.param(
            "/archive/", _personal_place_subject, _NO_MEMO, id="기록장_직접_등록_메모_없음"
        ),
        pytest.param(
            "/archive/statuses/",
            _personal_place_subject,
            _NO_MEMO,
            id="상태_목록_직접_등록_메모_없음",
        ),
        pytest.param(
            "/archive/statuses/",
            _official_event_subject,
            _OLD_MEMO_THEN_NEW_NO_MEMO,
            id="상태_목록_공식_행사_최신_기록만_메모_없음",
        ),
        pytest.param(
            "/archive/", _official_event_subject, _WITH_MEMO, id="기록장_공식_행사_메모_있음"
        ),
        pytest.param(
            "/archive/statuses/",
            _official_event_subject,
            _WITH_MEMO,
            id="상태_목록_공식_행사_메모_있음",
        ),
    ],
)
def test_방문_완료_행에_방문_기록이_있으면_메모와_상관없이_가장_최근_기록의_수정_링크가_나오고_기록_추가_링크는_나오지_않는다(
    user_client, path, build_subject, records
):
    user, client = user_client()
    subject = build_subject(user)
    UserEventStatus.objects.create(user=user, status=UserEventStatus.Status.VISITED, **subject)
    record_ids = {}
    for number, (visited_on, short_review) in enumerate(records, start=910_001):
        VisitRecord.objects.create(
            pk=number, user=user, visited_on=visited_on, short_review=short_review, **subject
        )
        record_ids[visited_on] = number
    newest_id = record_ids[max(record_ids)]
    older_ids = [number for number in record_ids.values() if number != newest_id]

    hrefs = _hrefs(client.get(path))

    assert f"/archive/visits/{newest_id}/edit/" in hrefs
    for older_id in older_ids:
        assert f"/archive/visits/{older_id}/edit/" not in hrefs
    assert not [href for href in hrefs if href.startswith("/archive/visits/new/?subject=")]


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("path", "build_subject", "subject_type"),
    [
        pytest.param("/archive/", _official_event_subject, "event", id="기록장_공식_행사"),
        pytest.param(
            "/archive/statuses/", _official_event_subject, "event", id="상태_목록_공식_행사"
        ),
        pytest.param("/archive/", _personal_place_subject, "personal", id="기록장_직접_등록"),
        pytest.param(
            "/archive/statuses/", _personal_place_subject, "personal", id="상태_목록_직접_등록"
        ),
    ],
)
def test_방문_완료_행에_방문_기록이_없으면_기록_추가_링크만_나오고_수정_링크는_나오지_않는다(
    user_client, path, build_subject, subject_type
):
    user, client = user_client()
    subject = build_subject(user)
    UserEventStatus.objects.create(user=user, status=UserEventStatus.Status.VISITED, **subject)
    subject_id = 920_001

    hrefs = _hrefs(client.get(path))

    assert f"/archive/visits/new/?subject={subject_type}:{subject_id}" in hrefs
    assert not [href for href in hrefs if re.fullmatch(r"/archive/visits/\d+/edit/", href)]


@pytest.mark.django_db
class TestVisitRecordCollectionShortcut:
    """다녀온 기록 (/archive/visits/) 카드에 굿즈 등록 바로가기가 붙는다
    (collection domain design plan §4 PR-C5b-2 CP-V1). 기존 수정/기록 삭제
    액션 옆에 ?visit_record=<id>로 컬렉션 등록 폼을 프리셀렉트하는 링크가
    붙는다 — test_방문_완료_행은_기록_바로가기_링크를_보여준다의 미러."""

    def test_다녀온_기록_카드는_컬렉션_등록_바로가기_링크를_보여준다(
        self, user_client, make_event, make_visit
    ):
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
