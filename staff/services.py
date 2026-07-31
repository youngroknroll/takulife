"""여러 도메인 앱을 넘나드는 스태프 전용 조율 로직.

events/services.py는 archive를 임포트할 수 없다(아키텍처 경계,
tests/test_architecture_boundaries.py 참고). 그런데 "이 행사를 완전히
지워도 안전한가"를 판단하려면 archive의 관련 모델들을 읽어야 한다.
staff는 events와 archive 양쪽에 의존해도 되는 계층이라 이 판단 로직이
events/services.py가 아닌 여기 있다.
"""
import logging

from events.services import hard_delete_event

logger = logging.getLogger(__name__)


class EventHasArchiveReferencesError(Exception):
    """archive 참조가 남아 있는 행사를 delete_event가 지우려 할 때 발생한다.

    관심/상태/방문 기록은 CASCADE라 그냥 지우면 사용자의 개인 기록이 함께
    사라진다. 컬렉션 아이템은 SET_NULL이라 살아남지만, 그 사실도 스태프가
    판단할 수 있도록 개수로 함께 알려준다.
    """

    def __init__(self, *, interest_count, status_count, visit_count, collection_item_count):
        self.interest_count = interest_count
        self.status_count = status_count
        self.visit_count = visit_count
        self.collection_item_count = collection_item_count
        super().__init__(
            "Event has archive references: "
            f"interest={interest_count}, status={status_count}, visit={visit_count}, "
            f"collection_item={collection_item_count}"
        )


def event_archive_reference_counts(*, event):
    """`event`를 참조하는 archive 쪽 레코드 개수를 종류별로 반환한다."""
    return {
        "interest": event.archive_user_interests.count(),
        "status": event.archive_user_statuses.count(),
        "visit": event.archive_user_visit_records.count(),
        "collection_item": event.archive_collection_items.count(),
    }


def delete_event(*, event):
    """archive 참조가 하나도 없을 때만 `event`를 완전히 지운다.

    참조가 남아 있으면 지우는 대신 EventHasArchiveReferencesError를
    낸다 — 그대로 지우면 사용자의 관심/상태/방문 기록이 CASCADE로 함께
    사라지기 때문이다.
    """
    counts = event_archive_reference_counts(event=event)
    if sum(counts.values()) > 0:
        raise EventHasArchiveReferencesError(
            interest_count=counts["interest"],
            status_count=counts["status"],
            visit_count=counts["visit"],
            collection_item_count=counts["collection_item"],
        )
    logger.info("Hard-deleting event pk=%s", event.pk)
    hard_delete_event(event=event)
