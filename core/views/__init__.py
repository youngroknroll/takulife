import logging
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import OperationalError, connection
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.decorators import api_view
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from archive.models import ActivityLogEntry, CollectionItem, PersonalEntry, UserEventStatus, VisitRecord
from archive.queries import (
    ARCHIVE_COLLECTION_PAGE_SIZE,
    ARCHIVE_INTEREST_PAGE_SIZE,
    ARCHIVE_PERSONAL_PAGE_SIZE,
    ARCHIVE_RECORD_PAGE_SIZE,
    ARCHIVE_STATUS_PAGE_SIZE,
    ARCHIVE_STATUS_SLUGS,
    ARCHIVE_VISIT_PAGE_SIZE,
    GOODS_ACQUIRED_KIND,
    SCHEDULE_KIND,
    VISIT_KIND,
    find_latest_activity_date_for_query,
    list_items_acquired_at_visit,
    list_user_activity_for_month,
    list_user_collection_items,
    list_user_interests,
    list_user_personal_entries,
    list_user_planned_events,
    list_user_statuses,
    list_user_unrecorded_visited_statuses,
    list_user_upcoming_planned_events,
    list_user_visit_records,
    user_collection_item_filter_values,
    user_collection_item_summary_counts,
    user_collection_item_work_title_facets,
    user_interest_count,
    user_interest_event_ids,
    user_interest_summary_counts,
    user_personal_entry_counts,
    user_personal_interest_ids,
    user_personal_statuses,
    user_status_counts,
    user_visit_category_values,
    user_visit_record_counts,
)
from core.calendar_grid import default_selected_date, month_grid
from core.models import HomeConfig
from core.vocab import (
    ARCHIVE_INTEREST_SORT,
    ARCHIVE_INTEREST_SORT_LABELS,
    ARCHIVE_PERSONAL_SORT,
    ARCHIVE_PERSONAL_SORT_LABELS,
    ARCHIVE_STATUS,
    ARCHIVE_STATUS_LABELS,
    ARCHIVE_STATUS_SORT,
    ARCHIVE_STATUS_SORT_LABELS,
    ARCHIVE_VISIT_SORT,
    ARCHIVE_VISIT_SORT_LABELS,
    archive_status_label,
    CATEGORY,
    CATEGORY_LABELS,
    COLLECTION_ITEM_TYPE,
    EVENT_SORT,
    EVENT_SORT_LABELS,
    EVENT_STATUS,
    EVENT_STATUS_LABELS,
    PERSONAL_ENTRY_CATEGORY_SUGGESTIONS,
    REGION,
    REGION_LABELS,
)
from events.models import Event
from events.presenters import derive_event_display, is_recently_added
from events.queries import (
    PUBLIC_LISTING_PAGE_SIZE,
    list_published_events,
    list_published_events_for_month,
    parse_public_listing_params,
)

from ._helpers import (
    _archive_query,
    _attach_display,
    _render_archive_list,
    _subject_view,
)
from .activity import activity_calendar
from .archive import (
    archive,
    archive_interests,
    archive_personal_entries,
    archive_personal_entry_create,
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

logger = logging.getLogger(__name__)


@login_required
def mypage(request):
    user = request.user
    saved_count = sum(user_status_counts(user).values())
    visit_count = user_visit_record_counts(user)["total_count"]
    personal_entry_count = user_personal_entry_counts(user)["total_count"]
    interest_count = user_interest_count(user)
    collection_count = user_collection_item_summary_counts(user)["total_count"]

    # index_rows drives mypage.html's index list; row order and ink values
    # are fixed by the mypage brief (§1). Each row is rendered as a single
    # <a> spanning the whole row, so its accessible name concatenates
    # title + badge + description + count. Whenever the title already
    # contains the badge label, keep domain_label empty below so the
    # template's "{% if row.domain_label %}" skips a badge that would
    # otherwise repeat the title for screen readers (BIR M3; exact-match
    # "내 활동"/"내 활동" is just the special case of this rule).
    index_rows = [
        {
            "title": "내 컬렉션",
            "domain_label": "컬렉션",
            "ink": "brand",
            "description": "모은 굿즈를 한눈에 확인해요",
            "count": collection_count,
            "unit": "점",
            "url": "/collection/",
        },
        {
            "title": "내 활동",
            "domain_label": "내 활동",
            "ink": "teal",
            "description": "저장한 행사를 모아봐요",
            "count": saved_count,
            "unit": "건",
            "url": "/archive/",
        },
        {
            "title": "다녀온 기록",
            "domain_label": "내 활동",
            "ink": "teal",
            "description": "다녀온 행사를 기록해요",
            "count": visit_count,
            "unit": "건",
            "url": "/archive/visits/",
        },
        {
            "title": "직접 등록",
            "domain_label": "내 활동",
            "ink": "teal",
            "description": "비공식 장소·행사를 등록해요",
            "count": personal_entry_count,
            "unit": "곳",
            "url": "/archive/personal/",
        },
        {
            "title": "찜 목록",
            "domain_label": "내 활동",
            "ink": "pink",
            "description": "관심 있는 행사를 찜해요",
            "count": interest_count,
            "unit": "건",
            "url": "/archive/interests/",
        },
    ]
    for row in index_rows:
        if row["domain_label"] and row["domain_label"] in row["title"]:
            row["domain_label"] = ""

    password_changed_at = user.password_changed_at
    password_changed_display = (
        timezone.localtime(password_changed_at).strftime("%Y.%m.%d")
        if password_changed_at is not None
        else "변경 이력 없음"
    )

    return render(
        request,
        "core/mypage.html",
        {
            "saved_count": saved_count,
            "visit_count": visit_count,
            "personal_entry_count": personal_entry_count,
            "interest_count": interest_count,
            "collection_count": collection_count,
            "joined_year": user.date_joined.year,
            "password_changed_at": password_changed_at,
            "password_changed_display": password_changed_display,
            "index_rows": index_rows,
        },
    )


def legal_privacy(request):
    return render(request, "core/legal/privacy.html")


def legal_terms(request):
    return render(request, "core/legal/terms.html")


@api_view(["GET"])
def api_root(request):
    return Response({"name": "takulife API"})


@api_view(["GET"])
def health(request):
    try:
        connection.ensure_connection()
    except OperationalError:
        return Response({"status": "error"}, status=503)
    return Response({"status": "ok"})
