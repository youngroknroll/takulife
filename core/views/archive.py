"""내 활동(아카이브) — 상태·방문 기록·직접 등록·찜 목록 뷰 모음."""

import uuid
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import ensure_csrf_cookie

from archive.models import PersonalEntry, VisitRecord
from archive.queries import (
    ARCHIVE_INTEREST_PAGE_SIZE,
    ARCHIVE_PERSONAL_PAGE_SIZE,
    ARCHIVE_RECORD_PAGE_SIZE,
    ARCHIVE_STATUS_PAGE_SIZE,
    ARCHIVE_STATUS_SLUGS,
    ARCHIVE_VISIT_PAGE_SIZE,
    list_items_acquired_at_visit,
    list_user_interests,
    list_user_personal_entries,
    list_user_planned_events,
    list_user_statuses,
    list_user_visit_records,
    list_visit_records_for_personal_entry,
    user_interest_summary_counts,
    user_personal_entry_counts,
    user_personal_interest_ids,
    user_personal_statuses,
    user_status_counts,
    user_visit_category_values,
    user_visit_record_counts,
)
from core.query_params import is_safe_pk_string
from core.vocab import (
    ARCHIVE_INTEREST_SORT,
    ARCHIVE_INTEREST_SORT_LABELS,
    ARCHIVE_PERSONAL_SORT,
    ARCHIVE_PERSONAL_SORT_LABELS,
    ARCHIVE_STATUS,
    ARCHIVE_STATUS_SORT,
    ARCHIVE_STATUS_SORT_LABELS,
    ARCHIVE_VISIT_SORT,
    ARCHIVE_VISIT_SORT_LABELS,
    archive_status_label,
    CATEGORY_LABELS,
    PERSONAL_ENTRY_CATEGORY_SUGGESTIONS,
)
from events.models import Event

from ._helpers import _archive_query, _attach_display, _render_archive_list, _subject_view
from .collection import _collection_item_row, _series_ink_classes


def _build_archive_status_rows(user_statuses):
    """archive 상태 항목(공식/비공식)의 표시 행을 만든다.

    status_id/slug/label과, Event와 PersonalEntry를 템플릿이 같은
    방식으로 렌더링할 수 있도록 균일하고 null 안전한 ``subject`` 뷰
    (비공식은 표시가 붙는다)를 담은 dict를 반환한다.
    """
    rows = []
    for us in user_statuses:
        subject = _subject_view(us)
        rows.append(
            {
                "status_id": us.pk,
                "status_slug": us.derived_status,
                "status_label": archive_status_label(us.derived_status),
                "label_visited": archive_status_label("visited"),
                "label_planned": archive_status_label("planned"),
                "subject": subject,
                "updated_at": us.updated_at,
                "review_text": us.review_text,
                "visit_record_id": us.visit_record_id,
            }
        )
    return rows


def _archive_status_context(
    user, selected_status, *, page_size, page_number, q: str = "", sort: str = ""
):
    """archive 대시보드와 상태 목록 페이지가 공유하는 컨텍스트를 만든다.

    두 페이지 모두 원본 저장 상태를 직접 읽지 않고 공유 조회 헬퍼로 똑같이
    'missed'를 유도한다. 요약 카운트는 필터 없이(전체 상태 집계)
    유지된다. 잘못된 상태 필터는 ""(전체)로 대체한다.

    상태 목록은 페이지네이션되며(``page_size``개씩), 현재 페이지 행만
    무거운 표시용 dict로 만든다. 두 페이지는 서로 다른 크기를 넘긴다
    (기록장 10, 예정 목록 5). ``has_statuses``는 현재 페이지가 아니라
    전체 매치 수를 반영해, 사용자가 정말로 하나도 없을 때만 빈 상태를
    보여준다. ``pager_query``는 페이지 링크를 넘나들 때도 상태 필터, q
    파라미터, 정렬을 보존한다.

    ``q``는 서버 쪽에서 상태 목록을 좁힌다(제목/위치 검색). 요약
    카운트(status_counts)는 항상 필터 없는 전체 값을 반영한다.
    ``has_any``는 현재 필터와 무관하게 사용자가 어떤 종류든 상태를 하나
    이상 가지고 있는지를 알려준다 — 템플릿이 "필터 결과가 없음"과 "진짜
    빈 archive"를 구분할 수 있게 한다.

    ``sort``는 list_user_statuses의 정렬을 고르며, 알 수 없는 값은
    (알 수 없는 상태가 ""로 대체되듯) ""(기본 정렬)로 대체된다.

    ``sort_query``(_archive_sort_link_query 경유)는 정렬 <details> 메뉴
    자체 링크를 위한, status/q만 담은 별도 꼬리다 — 위의
    pager_query/search_suffix와 달리 'sort'와 'page'를 제외하는데, 새
    정렬 값이 꼬리에 남아 있는 옛 값에 덮여쓰이지 않게 하기 위해서다.
    """
    if selected_status not in ARCHIVE_STATUS_SLUGS:
        selected_status = ""
    if sort not in ARCHIVE_STATUS_SORT_LABELS:
        sort = ""

    qs = list_user_statuses(user, selected_status, q=q, sort=sort)
    paginator = Paginator(qs, page_size)
    page_obj = paginator.get_page(page_number)
    status_rows = _build_archive_status_rows(page_obj.object_list)

    parts = []
    if selected_status:
        parts.append(("status", selected_status))
    if q:
        parts.append(("q", q))
    if sort:
        parts.append(("sort", sort))
    pager_query = "&" + urlencode(parts) if parts else ""
    # 필터 칩이 붙이는 꼬리로, 필터를 바꿔도 현재 검색을 유지한다
    # (urlencode라 한글/공백/&가 안전하다. 템플릿이 href 안 선행 &를
    # &amp;로 이스케이프하고 브라우저가 다시 디코딩한다).
    search_suffix_parts = [("q", q)] if q else []
    if sort:
        search_suffix_parts.append(("sort", sort))
    search_suffix = "&" + urlencode(search_suffix_parts) if search_suffix_parts else ""
    sort_query = _archive_sort_link_query(selected_status, q)

    counts = user_status_counts(user)
    return {
        "status_rows": status_rows,
        "page_obj": page_obj,
        "pager_query": pager_query,
        "search_suffix": search_suffix,
        "has_statuses": paginator.count > 0,
        "has_any": sum(counts.values()) > 0,
        "status_counts": counts,
        "selected_status": selected_status,
        "ARCHIVE_STATUS": ARCHIVE_STATUS,
        "q": q,
        "has_query": bool(q),
        "selected_sort": sort,
        "selected_sort_label": ARCHIVE_STATUS_SORT_LABELS[sort],
        "ARCHIVE_STATUS_SORT": ARCHIVE_STATUS_SORT,
        "sort_query": sort_query,
    }


def _archive_sort_link_query(selected_status, q):
    """현재 status/q 필터를 '&key=value' 쿼리스트링 꼬리로 반환한다
    (선행 '&', templates/core/partials/_pager.html의 extra_query 관례와
    동일) — archive 정렬 <details> 메뉴의 '?sort=<value>...' 링크가
    붙이는 용도다.

    _archive_status_context 자체의 pager_query/search_suffix(페이지네이션
    /검색을 넘나들며 현재 정렬을 보존해야 해서 일부러 'sort'를 포함한다)와
    달리, 여기선 일부러 'sort'와 'page'를 제외한다. 정렬 링크는 이미
    '?sort=<새 값>'으로 시작하므로 pager_query의 꼬리를 그대로 쓰면
    'sort' 키가 중복되고(?sort=NEW&status=...&sort=OLD),
    QueryDict.get()은 마지막 값을 반환해 새 정렬이 조용히 버려진다.
    'page'를 제외하는 이유는 새 정렬을 고르면 목록이 1페이지로
    돌아가야 하기 때문이다(_calendar_extra_query가 같은 이유로 자신의
    페이지 관련 파라미터를 제외하는 것과 같다).
    """
    parts = []
    if selected_status:
        parts.append(("status", selected_status))
    if q:
        parts.append(("q", q))
    return "&" + urlencode(parts) if parts else ""


@login_required
@ensure_csrf_cookie
def archive(request):
    context = _archive_status_context(
        request.user,
        request.GET.get("status", ""),
        page_size=ARCHIVE_RECORD_PAGE_SIZE,
        page_number=request.GET.get("page"),
        q=_archive_query(request),
        sort=request.GET.get("sort", ""),
    )
    return _render_archive_list(
        request,
        full_template="core/archive/index.html",
        fragment_template="core/partials/_archive_results_record.html",
        context=context,
    )


@login_required
@ensure_csrf_cookie
def archive_statuses(request):
    context = _archive_status_context(
        request.user,
        request.GET.get("status", ""),
        page_size=ARCHIVE_STATUS_PAGE_SIZE,
        page_number=request.GET.get("page"),
        q=_archive_query(request),
        sort=request.GET.get("sort", ""),
    )
    return _render_archive_list(
        request,
        full_template="core/archive/statuses.html",
        fragment_template="core/partials/_archive_results_statuses.html",
        context=context,
    )


@login_required
@ensure_csrf_cookie
def archive_visits(request):
    user = request.user
    q = _archive_query(request)
    raw_filter = request.GET.get("filter", "")
    sort = request.GET.get("sort", "")
    if sort not in ARCHIVE_VISIT_SORT_LABELS:
        sort = ""

    # --- 사용자의 전체 방문 기록에서 뽑은 카테고리 칩 -----------------------
    # 현재 페이지가 아니라 전체 데이터셋을 써서 페이지가 바뀌어도 칩이
    # 안정적으로 유지된다. 라벨은 여기서 해석해 archive/queries.py가
    # core.vocab을 임포트하지 않게 한다(순환 의존 방지).
    pairs = user_visit_category_values(user)
    categories = []
    seen_labels: set = set()
    for event_cat, personal_cat in pairs:
        if event_cat:
            label = CATEGORY_LABELS.get(event_cat, event_cat)
        elif personal_cat:
            label = personal_cat
        else:
            continue
        if label not in seen_labels:
            categories.append(label)
            seen_labels.add(label)
    # 쌍에서 어느 FK가 null인지로 축의 존재 여부를 판단한다 — event가
    # 없으면(비공식) event__category 컬럼이 None이고, personal_entry가
    # 없으면(공식) personal_entry__category가 None이다. truthy 여부가
    # 아니라 None 여부로 판단해야 공식 행사의 카테고리가 빈 문자열일 때
    # 잘못 걸러지지 않는다.
    has_unofficial = any(event_cat is None for event_cat, _ in pairs)
    has_official = any(personal_cat is None for _, personal_cat in pairs)

    # --- 화이트리스트 검사가 있는 필터 파싱 --------------------------------
    # 알 수 없는 값은 필터 없음으로 대체한다(500 방지).
    official = None
    category_codes: tuple = ()
    category_label = ""

    if raw_filter == "unofficial":
        official = False
    elif raw_filter.startswith("cat:"):
        label = raw_filter[4:]
        if label and label in categories:
            category_label = label
            category_codes = tuple(
                code for code, lbl in CATEGORY_LABELS.items() if lbl == label
            )
        # else: 라벨이 비었거나 화이트리스트에 없음 → 필터 없음으로 대체

    selected_filter = raw_filter if (official is not None or category_label) else ""

    # --- 필터 없는 전체 기준 요약 카운트 -----------------------------------
    # 활성 필터와 무관하게 사용자의 전체 방문 기록을 보고해, 요약
    # 카드가 헷갈리게 줄어드는 일이 없게 한다.
    visit_counts = user_visit_record_counts(user)
    total_count = visit_counts["total_count"]
    memo_count = visit_counts["memo_count"]

    # --- 필터링 + 페이지네이션된 결과 집합 ----------------------------------
    filtered_qs = list_user_visit_records(
        user,
        official=official,
        category_codes=category_codes,
        category_label=category_label,
        q=q,
        sort=sort,
    )
    paginator = Paginator(filtered_qs, ARCHIVE_VISIT_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    visit_rows = [
        {
            "record_id": record.pk,
            "visited_on": record.visited_on,
            "short_review": record.short_review,
            "subject": _subject_view(record),
            "photos": list(record.photos.all()),
        }
        for record in page_obj.object_list
    ]

    # --- 페이저 쿼리스트링 --------------------------------------------------
    parts = []
    if selected_filter:
        parts.append(("filter", selected_filter))
    if q:
        parts.append(("q", q))
    if sort:
        parts.append(("sort", sort))
    pager_query = "&" + urlencode(parts) if parts else ""
    # 필터 칩이 붙이는 꼬리로, 필터를 바꿔도 현재 검색을 유지한다.
    search_suffix_parts = [("q", q)] if q else []
    if sort:
        search_suffix_parts.append(("sort", sort))
    search_suffix = "&" + urlencode(search_suffix_parts) if search_suffix_parts else ""

    return _render_archive_list(
        request,
        full_template="core/archive/visits.html",
        fragment_template="core/partials/_archive_results_visits.html",
        context={
            "visit_rows": visit_rows,
            "page_obj": page_obj,
            "total_count": total_count,
            "memo_count": memo_count,
            "has_visits": total_count > 0,
            "categories": categories,
            "has_unofficial": has_unofficial,
            "has_official": has_official,
            "selectable_events": list_user_planned_events(user),
            "selectable_personal_entries": list_user_personal_entries(
                user, kind=PersonalEntry.Kind.PLACE
            ),
            "q": q,
            "has_query": bool(q),
            "selected_filter": selected_filter,
            "pager_query": pager_query,
            "search_suffix": search_suffix,
            "selected_sort": sort,
            "selected_sort_label": ARCHIVE_VISIT_SORT_LABELS[sort],
            "ARCHIVE_VISIT_SORT": ARCHIVE_VISIT_SORT,
        },
    )


def _parse_visit_preselect(request):
    """방문 기록 작성 폼을 위해, 선택적인 ?subject=event:<id> / personal:<id>를
    잠긴 대상으로 해석한다.

    파라미터가 공개된 행사나 요청자 본인의 비공식 등록을 가리키면
    ``{"value": "event:5", "label": "이벤트명"}``을, 아니면 ``None``을
    반환한다(그러면 폼이 선택 드롭다운으로 대체된다). 이미 방문한
    행사(예정 전용 드롭다운엔 없다)의 '기록' 버튼으로도 기록을 남길 수
    있게 해준다 — 방문 API는 공개된 어떤 행사든 받아준다. id는 여기서
    검증하므로 템플릿은 이를 신뢰된 잠금 필드로 렌더링할 수 있다.
    """
    kind, _, ident = request.GET.get("subject", "").partition(":")
    if not is_safe_pk_string(ident):
        return None
    pk = int(ident)
    if kind == "event":
        event = Event.objects.published().filter(pk=pk).first()
        if event is not None:
            return {"value": f"event:{event.pk}", "label": event.title}
    elif kind == "personal":
        entry = PersonalEntry.objects.filter(
            pk=pk, user=request.user, kind=PersonalEntry.Kind.PLACE
        ).first()
        if entry is not None:
            return {"value": f"personal:{entry.pk}", "label": entry.title}
    return None


@login_required
@ensure_csrf_cookie
def archive_visit_create(request):
    """방문 기록 생성 전용 작성 페이지.

    렌더링만 하는 뷰다: 폼은 visit_create.js의 기존 JSON/사진 API로
    제출된다. 대상 선택지는 이 페이지가 대체한 인라인 폼과 같되,
    ``?subject=``가 특정 대상을 미리 지정하면(예: 방문 완료 이벤트의
    '기록' 버튼에서) 드롭다운 대신 그 대상을 잠근 채로 보여준다.
    """
    # 폼을 렌더링할 때마다 한 번씩 발급해 숨은 input에 담는다 — 이 토큰이
    # bfcache DOM 스냅샷에서도 살아남아 재전송 방지용 멱등 키로 쓰인다.
    return render(
        request,
        "core/archive/visit_create.html",
        {
            "selectable_events": list_user_planned_events(request.user),
            "selectable_personal_entries": list_user_personal_entries(
                request.user, kind=PersonalEntry.Kind.PLACE
            ),
            "preselect": _parse_visit_preselect(request),
            "client_token": uuid.uuid4(),
        },
    )


@login_required
@ensure_csrf_cookie
def archive_visit_edit(request, record_id):
    """방문 기록 하나를 수정하는 페이지(소유자 한정).

    날짜/메모를 미리 채우고 기존 사진을 나열한다. 수정은 visit_edit.js의
    PATCH/사진 API로 이뤄진다. 대상은 읽기 전용으로 표시된다.
    """
    record = get_object_or_404(VisitRecord, pk=record_id, user=request.user)
    return render(
        request,
        "core/archive/visit_edit.html",
        {
            "record_id": record.pk,
            "subject": _subject_view(record),
            "visited_on": record.visited_on,
            "short_review": record.short_review,
            "photos": list(record.photos.all().order_by("id")),
        },
    )


@login_required
@ensure_csrf_cookie
def archive_visit_detail(request, record_id):
    """방문 기록 하나의 읽기 전용 상세 페이지(소유자 한정).

    방문의 대상, 날짜, 메모, 사진, 그 방문에서 획득한 CollectionItem
    (archive/queries.list_items_acquired_at_visit)을 보여준다 — archive
    내부의 역방향 FK 조회일 뿐 새로운 도메인 간 결합은 아니다.
    이 페이지의 삭제 동작에 CSRF 쿠키가 필요해 (수정 페이지뿐 아니라)
    여기도 ``@ensure_csrf_cookie``가 필요하다.
    """
    record = get_object_or_404(VisitRecord, pk=record_id, user=request.user)
    goods = list_items_acquired_at_visit(record)
    series_ink_classes = _series_ink_classes([item.work_title for item in goods])
    return render(
        request,
        "core/archive/visit_detail.html",
        {
            "record_id": record.pk,
            "subject": _subject_view(record),
            "visited_on": record.visited_on,
            "short_review": record.short_review,
            "photos": list(record.photos.all().order_by("id")),
            "goods_rows": [_collection_item_row(item, series_ink_classes) for item in goods],
            "goods_count": len(goods),
        },
    )


@login_required
@ensure_csrf_cookie
def archive_personal_entries(request):
    user = request.user
    q = _archive_query(request)
    sort = request.GET.get("sort", "")
    if sort not in ARCHIVE_PERSONAL_SORT_LABELS:
        sort = ""

    # 요약 카운트는 항상 필터 없는 전체 집합에서 가져와, 헤더 카드가
    # 활성 검색과 무관하게 사용자의 전체 컬렉션을 보고한다.
    entry_counts = user_personal_entry_counts(user)
    total_count = entry_counts["total_count"]
    visit_linked_count = entry_counts["visit_linked_count"]
    has_entries = total_count > 0

    # 페이지 쿼리셋은 q가 있으면 필터링한 뒤 페이지네이션한다.
    page_qs = list_user_personal_entries(user, q=q, sort=sort)
    paginator = Paginator(page_qs, ARCHIVE_PERSONAL_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    interest_map = user_personal_interest_ids(user)
    status_map = user_personal_statuses(user)

    entry_rows = []
    for entry in page_obj.object_list:
        status_slug, status_id = status_map.get(entry.id, ("", None))
        entry_rows.append(
            {
                "entry": entry,
                "is_place": entry.kind == PersonalEntry.Kind.PLACE,
                "interest_id": interest_map.get(entry.id),
                "status_slug": status_slug,
                "status_id": status_id,
                "status_label": archive_status_label(status_slug) if status_slug else "",
                "planned_label": archive_status_label("planned"),
                "is_submitted": entry.promotion_status == PersonalEntry.PromotionStatus.SUBMITTED,
            }
        )

    # 페이저 쿼리스트링은 활성 검색과 기본이 아닌 정렬을 모두 보존한다
    # — 위 archive_visits의 parts 리스트 패턴과 동일.
    parts = []
    if q:
        parts.append(("q", q))
    if sort:
        parts.append(("sort", sort))
    pager_query = "&" + urlencode(parts) if parts else ""

    return _render_archive_list(
        request,
        full_template="core/archive/personal_entries.html",
        fragment_template="core/partials/_archive_results_personal.html",
        context={
            "entry_rows": entry_rows,
            "total_count": total_count,
            "visit_linked_count": visit_linked_count,
            "has_entries": has_entries,
            "page_obj": page_obj,
            "pager_query": pager_query,
            "q": q,
            "has_query": bool(q),
            "selected_sort": sort,
            "selected_sort_label": ARCHIVE_PERSONAL_SORT_LABELS[sort],
            "ARCHIVE_PERSONAL_SORT": ARCHIVE_PERSONAL_SORT,
        },
    )


@login_required
@ensure_csrf_cookie
def archive_personal_entry_create(request):
    """렌더링만 하는 뷰다: 폼은 새 엔드포인트가 아니라 기존 비공식 등록
    JSON API(`/api/personal-entries/`)로 제출된다 — archive_collection_
    item_create의 렌더링 전용 구조와 같다. 컨텍스트에 담긴
    PERSONAL_ENTRY_CATEGORY_SUGGESTIONS는 자유 입력을 돕는 힌트 칩일
    뿐(`choices` 제약이 아니다 — 필드는 계속 자유 텍스트다)."""
    # 폼을 렌더링할 때마다 한 번씩 발급해 숨은 input에 담는다 — 이 토큰이
    # bfcache DOM 스냅샷에서도 살아남아 재전송 방지용 멱등 키로 쓰인다.
    return render(
        request,
        "core/archive/personal_create.html",
        {
            "PERSONAL_ENTRY_CATEGORY_SUGGESTIONS": PERSONAL_ENTRY_CATEGORY_SUGGESTIONS,
            "client_token": uuid.uuid4(),
        },
    )


@login_required
def archive_personal_entry_detail(request, entry_id):
    """PersonalEntry 하나의 읽기 전용 상세 페이지(소유자 한정)."""
    entry = get_object_or_404(PersonalEntry, pk=entry_id, user=request.user)
    interest_map = user_personal_interest_ids(request.user)
    status_map = user_personal_statuses(request.user)
    status_slug, status_id = status_map.get(entry.id, ("", None))
    visit_records = list_visit_records_for_personal_entry(entry)
    return render(
        request,
        "core/archive/personal_detail.html",
        {
            "entry": entry,
            "interest_id": interest_map.get(entry.id),
            "status_slug": status_slug,
            "status_id": status_id,
            "status_label": archive_status_label(status_slug) if status_slug else "",
            "planned_label": archive_status_label("planned"),
            "is_submitted": entry.promotion_status == PersonalEntry.PromotionStatus.SUBMITTED,
            # 라벨-필드 매핑만 뷰가 소유하고, 지역화된 날짜 표기는 템플릿 |date: 필터가 담당
            "record_info_rows": [
                {"label": "등록일", "value": entry.created_at},
                {"label": "마지막 수정", "value": entry.updated_at},
            ],
            "visit_records": visit_records,
            "visit_records_count": len(visit_records),
        },
    )


@login_required
def archive_personal_entry_edit(request, entry_id):
    """렌더링만 하는 수정 페이지(소유자 한정). 저장은 archive_collection_
    item_edit과 마찬가지로 기존 DRF PATCH(`/api/personal-entries/<id>/`)로
    이뤄진다. 컨텍스트의 PERSONAL_ENTRY_CATEGORY_SUGGESTIONS는
    archive_personal_entry_create와 같이 자유 입력 힌트 칩일 뿐(`choices`
    제약 아님)."""
    entry = get_object_or_404(PersonalEntry, pk=entry_id, user=request.user)
    return render(
        request,
        "core/archive/personal_edit.html",
        {
            "entry": entry,
            "PERSONAL_ENTRY_CATEGORY_SUGGESTIONS": PERSONAL_ENTRY_CATEGORY_SUGGESTIONS,
        },
    )


@login_required
@ensure_csrf_cookie
def archive_interests(request):
    user = request.user
    q = _archive_query(request)
    sort = request.GET.get("sort", "")
    if sort not in ARCHIVE_INTEREST_SORT_LABELS:
        sort = ""

    # --- 필터 없는 전체 기준 요약 카운트 -----------------------------------
    # 활성 검색과 무관하게 사용자의 전체 찜 목록을 설명한다 — 다른 탭들의
    # 요약 카드 동작과 동일하다.
    counts = user_interest_summary_counts(user)
    interest_count = counts["interest_count"]
    ongoing_count = counts["ongoing_count"]
    planned_overlap_count = counts["planned_overlap_count"]

    # --- 필터링 + 페이지네이션된 결과 집합 ----------------------------------
    filtered_qs = list_user_interests(user, q=q, sort=sort)
    paginator = Paginator(filtered_qs, ARCHIVE_INTEREST_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))
    page_interests = list(page_obj.object_list)

    # 공식(행사 연결) 행들은 행마다 부르지 않고(N+1이 된다)한 번에
    # _attach_display로 묶어 처리한 뒤 event id로 다시 매핑한다.
    official_events = [
        interest.event for interest in page_interests if interest.event_id
    ]
    display_by_event_id = {
        display["event"].id: display
        for display in _attach_display(official_events, user=user)
    }

    interest_rows = []
    for interest in page_interests:
        if interest.event_id:
            display = display_by_event_id[interest.event_id]
            user_status = display["user_status"]
            interest_rows.append(
                {
                    "interest_id": interest.pk,
                    "subject": _subject_view(interest),
                    "status": display["status_slug"],
                    "dday": display["dday"],
                    "user_status": user_status,
                    # 조회자가 이 행사에 아직 상태가 없을 때만 방문 예정을
                    # 제안한다 — 이미 추적 중인 행(예: 방문 완료)에 공용
                    # 상태 버튼을 두면 기존 기록을 조용히 덮어쓴다. 이미
                    # 끝난 행사도 제외한다 — 끝난 행사의 방문을 계획하는
                    # 건 의미가 없고, 종료된 행에는 이 버튼을 보여주지
                    # 않기로 설계됐다.
                    "can_plan": user_status == "" and display["status_slug"] != "ended",
                }
            )
        else:
            interest_rows.append(
                {
                    "interest_id": interest.pk,
                    "subject": _subject_view(interest),
                    "status": None,
                    "dday": None,
                    "user_status": None,
                    "can_plan": False,
                }
            )

    # --- 페이저 쿼리스트링 --------------------------------------------------
    parts = []
    if q:
        parts.append(("q", q))
    if sort:
        parts.append(("sort", sort))
    pager_query = "&" + urlencode(parts) if parts else ""

    return _render_archive_list(
        request,
        full_template="core/archive/interests.html",
        fragment_template="core/partials/_archive_results_interests.html",
        context={
            "interest_rows": interest_rows,
            "interest_count": interest_count,
            "ongoing_count": ongoing_count,
            "planned_overlap_count": planned_overlap_count,
            "has_interests": interest_count > 0,
            "page_obj": page_obj,
            "q": q,
            "has_query": bool(q),
            "pager_query": pager_query,
            "selected_sort": sort,
            "selected_sort_label": ARCHIVE_INTEREST_SORT_LABELS[sort],
            "ARCHIVE_INTEREST_SORT": ARCHIVE_INTEREST_SORT,
        },
    )
