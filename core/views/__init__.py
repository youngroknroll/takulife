"""core 뷰 패키지. 도메인별 서브모듈을 순수 재노출만 한다."""
from .account import delete_account, mypage
from .activity import activity_calendar
from .archive import (
    archive,
    archive_interests,
    archive_personal_entries,
    archive_personal_entry_create,
    archive_personal_entry_detail,
    archive_personal_entry_edit,
    archive_statuses,
    archive_visit_create,
    archive_visit_detail,
    archive_visit_edit,
    archive_visits,
)
from .collection import (
    archive_collection_item_create,
    archive_collection_item_detail,
    archive_collection_item_edit,
    archive_collection_items,
)
from .events import event_calendar, event_detail, event_list, home
from .legal import legal_privacy, legal_terms
from .system import api_root, health

__all__ = [
    "home",
    "event_list",
    "event_calendar",
    "event_detail",
    "archive",
    "archive_statuses",
    "archive_visits",
    "archive_visit_create",
    "archive_visit_edit",
    "archive_visit_detail",
    "activity_calendar",
    "archive_collection_items",
    "archive_collection_item_create",
    "archive_collection_item_edit",
    "archive_collection_item_detail",
    "archive_personal_entries",
    "archive_personal_entry_create",
    "archive_personal_entry_detail",
    "archive_personal_entry_edit",
    "archive_interests",
    "mypage",
    "delete_account",
    "legal_privacy",
    "legal_terms",
    "api_root",
    "health",
]
