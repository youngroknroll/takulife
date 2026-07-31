"""core.models.AnalyticsEvent 검증
(.docs/plans/2026-07-14-stage0-deployment-foundation-plan.md §8).
"""
import pytest
from django.core.exceptions import ValidationError

from core.models import AnalyticsEvent

pytestmark = pytest.mark.domain


ALLOWED_EVENT_NAMES = [
    "event_list_viewed",
    "event_searched",
    "event_detail_viewed",
    "event_interested",
    "event_planned",
    "event_marked_visited",
    "visit_record_created",
    "visit_photo_added",
    "collection_item_created",
    "collection_item_updated",
    "collection_item_linked_to_visit",
    "collection_item_marked_wanted",
    "collection_item_marked_tradeable",
]

ALLOWED_EVENT_NAME_IDS = [
    "행사_목록_조회",
    "행사_검색",
    "행사_상세_조회",
    "행사_관심_등록",
    "행사_방문_예정_등록",
    "행사_다녀옴_표시",
    "방문_기록_생성",
    "방문_사진_추가",
    "컬렉션_항목_생성",
    "컬렉션_항목_수정",
    "컬렉션_항목_방문_연결",
    "컬렉션_항목_찜_표시",
    "컬렉션_항목_교환가능_표시",
]


@pytest.mark.django_db
@pytest.mark.parametrize("event_name", ALLOWED_EVENT_NAMES, ids=ALLOWED_EVENT_NAME_IDS)
def test_애널리틱스_이벤트는_허용된_이벤트명이면_유효성_검증을_통과한다(event_name):
    event = AnalyticsEvent(event_name=event_name, user_key="abc123")

    event.full_clean()


@pytest.mark.django_db
def test_애널리틱스_이벤트는_알수없는_이벤트명이면_유효성_검증에_실패한다():
    event = AnalyticsEvent(event_name="not_a_real_event", user_key="abc123")

    with pytest.raises(ValidationError):
        event.full_clean()
