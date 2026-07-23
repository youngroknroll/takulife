"""컨텍스트 필드 계약 고정 (활동 페이지 리디자인 §E).

_subject_view / _build_archive_status_rows는 여러 아카이브 페이지가 공유하는
헬퍼다. 리디자인 시안이 요구하는 두 표시 필드가 신규 쿼리·조인 없이 이미
스코프에 있는 값으로부터 컨텍스트에 담기는지만 고정한다:
- subject.category_slug — 공식 이벤트의 원본 category 값(라벨이 아닌 slug)
- status row.updated_at — UserEventStatus.updated_at
"""
from datetime import datetime

import pytest
from django.utils import timezone

from archive.models import UserEventStatus

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_상태_행의_공식_이벤트_subject에_category_slug가_원본_카테고리로_담긴다(
    user_client, make_event, make_status
):
    user, client = user_client()
    event = make_event(title="코스프레 행사", category="cosplay")
    make_status(user, event=event, status="planned")

    resp = client.get("/archive/statuses/")

    assert resp.status_code == 200
    rows = resp.context["status_rows"]
    assert len(rows) == 1
    assert rows[0]["subject"]["category_slug"] == "cosplay"


@pytest.mark.django_db
def test_상태_행에_updated_at이_담긴다(user_client, make_event, make_status):
    user, client = user_client()
    event = make_event(title="행사")
    status = make_status(user, event=event, status="planned")

    resp = client.get("/archive/statuses/")

    assert resp.status_code == 200
    rows = resp.context["status_rows"]
    assert len(rows) == 1
    assert rows[0]["updated_at"] == status.updated_at


@pytest.mark.django_db
def test_정렬_쿼리스트링을_전달하면_예정_목록_페이지_순서가_바뀐다(
    user_client, make_event, make_status
):
    user, client = user_client()
    event_a = make_event(title="먼저 등록, 나중 수정")
    event_b = make_event(title="나중 등록, 이후 수정 없음")

    status_a = make_status(user, event=event_a, status="planned")
    status_b = make_status(user, event=event_b, status="planned")

    UserEventStatus.objects.filter(pk=status_a.pk).update(
        created_at=timezone.make_aware(datetime(2026, 6, 1)),
        updated_at=timezone.make_aware(datetime(2026, 6, 20)),
    )
    UserEventStatus.objects.filter(pk=status_b.pk).update(
        created_at=timezone.make_aware(datetime(2026, 6, 15)),
        updated_at=timezone.make_aware(datetime(2026, 6, 10)),
    )

    resp = client.get("/archive/statuses/?sort=created_at")

    assert resp.status_code == 200
    rows = resp.context["status_rows"]
    assert [row["status_id"] for row in rows] == [status_b.pk, status_a.pk]


@pytest.mark.django_db
def test_상태_행_컨텍스트에_최신_방문기록의_리뷰와_id가_담긴다(
    user_client, make_event, make_status, make_visit
):
    user, client = user_client()
    event = make_event(title="방문 행사")
    make_status(user, event=event, status="visited")
    visit = make_visit(
        user, event=event, visited_on="2026-06-01", short_review="좋았어요"
    )

    resp = client.get("/archive/statuses/")

    assert resp.status_code == 200
    rows = resp.context["status_rows"]
    assert len(rows) == 1
    assert rows[0]["review_text"] == "좋았어요"
    assert rows[0]["visit_record_id"] == visit.id
