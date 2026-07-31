# 컬렉션(보유 굿즈) 목록·생성·수정·상세 뷰 모음.
import uuid
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import ensure_csrf_cookie

from archive.models import CollectionItem, VisitRecord
from archive.queries import (
    ARCHIVE_COLLECTION_PAGE_SIZE,
    list_user_collection_items,
    list_user_visit_records,
    user_collection_item_filter_values,
    user_collection_item_summary_counts,
    user_collection_item_work_title_facets,
)
from core.query_params import is_safe_pk_string
from core.vocab import COLLECTION_ITEM_TYPE

from ._helpers import _archive_query, _render_archive_list, _subject_view

SERIES_INK_COUNT = 12
# SERIES_INK_COUNT와 서로소여야 한다 — 공약수가 있으면 팔레트 일부만
# 순회해 12개 작품보다 훨씬 전에 충돌이 다시 생긴다.
SERIES_INK_STRIDE = 5


def _series_ink_classes(titles_in_registration_order) -> dict[str, str]:
    """각 work_title에 해시가 아니라 최초 등록 순서로 강조색 버킷
    ("gi-1".."gi-{SERIES_INK_COUNT}")을 배정한다.

    이전 방식인 문자열 해시 기반은 버킷 수를 늘려도 생일 역설 때문에
    여전히 충돌한다 — SERIES_INK_COUNT=12 버킷이면 서로 다른 work_title
    5개만 있어도 둘이 같은 버킷에 떨어질 확률이 약 62%다. 대신 위치로
    배정하면 서로 다른 work_title 수가 SERIES_INK_COUNT 이내인 한
    충돌이 수학적으로 불가능하다.

    순서는 반드시 등록 순서(먼저 등록된 first_id가 앞)여야지, 개수 내림차순
    표시 순서면 안 된다: 개수로 정렬하면 컬렉션 어디에 항목이 추가되든
    개수 순위가 바뀌면서 work_title의 색이 흔들린다. 최초 등록순으로
    정렬해야 work_title의 색이 평생 안정적으로 유지된다.

    연속 등록은 인접 버킷이 아니라 SERIES_INK_STRIDE만큼 색상환에서
    퍼뜨려 배정한다. 팔레트가 색상환을 순서대로 훑기 때문에 버킷 N과
    N+1은 8px 점에서 가장 구분하기 어려운 30° 차이 쌍인데, 연속 등록이
    바로 흔한 경우다. 5칸씩 건너뛰면 사용자의 첫 두 작품이 30°가 아니라
    150° 떨어진다. 이 보폭은 SERIES_INK_COUNT와 서로소라 매핑이 여전히
    전단사이고 무충돌 보장도 그대로 유지된다.

    SERIES_INK_COUNT를 넘는 제목은 다시 "gi-1"부터 순환한다.
    """
    return {
        title: f"gi-{index * SERIES_INK_STRIDE % SERIES_INK_COUNT + 1}"
        for index, title in enumerate(titles_in_registration_order)
    }


def _collection_item_row(item, series_ink_classes):
    """CollectionItem 카드 하나의 표시 행.

    해당 개수가 0이면 ``quantity_label``/``tradeable_label``은 ""(배지
    없음)이다 — quantity=0인 구함 전용 항목은 "수량 0개"가 아니라
    숫자 배지 없이 렌더링된다.

    ``series_ink_classes``는 _series_ink_classes()가 만든 {work_title:
    class} 맵이다. 빈 work_title은 그 맵의 키가 될 수 없어(facet 쿼리가
    제외한다) .get(..., "gi-0")가 별도 빈 값 검사 없이 시리즈 없음
    버킷으로 자연스럽게 빠진다.

    ``badges``는 templates/core/partials/_collection_badges.html이
    쓰는 고정 순서(보유 -> 구함 -> 교환) 배지 목록이다. 네 곳의 템플릿
    소비처가 각자 ``item.quantity > 0``을 다시 계산하지 않도록 여기서
    한 번만 계산한다(그 중복이 원래 보유/구함 축 버그를 숨겼었다).
    DB 수준에서 ``tradeable=True``는 항상 ``owned=True``를 함의하므로
    (tradeable_quantity <= quantity) "보유 안 함, 교환 가능" 분기는
    도달 불가능하며 여기 일부러 코드 경로를 두지 않았다.
    """
    owned = item.quantity > 0
    wanted = item.is_wanted
    tradeable = item.tradeable_quantity > 0
    if owned or wanted or tradeable:
        badges = []
        if owned:
            badges.append({"tone": "owned", "label": "보유"})
        if wanted:
            badges.append({"tone": "wanted", "label": "구함"})
        if tradeable:
            badges.append({"tone": "tradeable", "label": "교환"})
    else:
        badges = [{"tone": "none", "label": "미보유"}]

    return {
        "item": item,
        "quantity_label": f"수량 {item.quantity}개" if item.quantity > 0 else "",
        "tradeable_label": (
            f"교환 가능 {item.tradeable_quantity}개" if item.tradeable_quantity > 0 else ""
        ),
        "is_wanted": item.is_wanted,
        "badges": badges,
        "series_ink_class": series_ink_classes.get(item.work_title, "gi-0"),
    }


@login_required
@ensure_csrf_cookie
def archive_collection_items(request):
    # 옛 북마크 호환: ?is_wanted=false가 예전엔 보유 탭의 URL 그 자체였다.
    # 이제 보유가 독립된 축이 됐으므로, 북마크된 ?is_wanted=false 링크는
    # ?owned=true로 넘겨야 과소 집계(보유+구함 행이 예전엔 제외됐다)를
    # 멈춘다. owned가 이미 있으면 건너뛴다 — 명시적 owned 값은 호출자가
    # 이미 새 축에서 의도적으로 선택했다는 뜻이라 이 보정이 덮어쓰면 안
    # 된다. 리다이렉트되는 요청은 DB를 건드릴 이유가 없으므로 조회 작업
    # 전에 배치한다.
    if request.GET.get("is_wanted") == "false" and "owned" not in request.GET:
        redirect_params = request.GET.copy()
        del redirect_params["is_wanted"]
        redirect_params["owned"] = "true"
        return redirect(f"{request.path}?{redirect_params.urlencode()}")

    user = request.user
    q = _archive_query(request)
    work_title = request.GET.get("work_title", "")
    character_name = request.GET.get("character_name", "")
    item_type = request.GET.get("item_type", "")
    # 알 수 없는 값(값이 없는 경우 포함)은 "필터 없음"을 뜻한다 —
    # visits/personal-entries의 필터 대체 규칙과 동일(500 방지).
    is_wanted = {"true": True, "false": False}.get(request.GET.get("is_wanted", ""))
    is_wanted_value = {True: "true", False: "false"}.get(is_wanted, "")
    duplicate = {"true": True, "false": False}.get(request.GET.get("duplicate", ""))
    duplicate_value = {True: "true", False: "false"}.get(duplicate, "")
    tradeable = {"true": True, "false": False}.get(request.GET.get("tradeable", ""))
    tradeable_value = {True: "true", False: "false"}.get(tradeable, "")
    owned = {"true": True, "false": False}.get(request.GET.get("owned", ""))
    owned_value = {True: "true", False: "false"}.get(owned, "")
    # "list"만 인식한다. 값이 없거나 다른 값이면 기본 갤러리 뷰로
    # 대체한다(위와 같은 500 방지 규칙).
    view_mode = "list" if request.GET.get("view") == "list" else "gallery"

    summary_counts = user_collection_item_summary_counts(user)
    has_items = summary_counts["total_count"] > 0

    filtered_qs = list_user_collection_items(
        user,
        work_title=work_title,
        character_name=character_name,
        item_type=item_type,
        is_wanted=is_wanted,
        duplicate=duplicate,
        tradeable=tradeable,
        owned=owned,
        q=q,
    )
    paginator = Paginator(filtered_qs, ARCHIVE_COLLECTION_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))

    # 필터·페이지로 좁혀진 부분집합이 아니라 컬렉션 전체에 대한 facet
    # 조회 하나가 사이드바 카운트와 시리즈별 색상 팔레트를 모두
    # 만든다 — 그래야 어떤 페이지·필터·검색으로 보든 같은 work_title이
    # 항상 같은 색을 가진다.
    work_title_facets = user_collection_item_work_title_facets(user)
    palette_titles = [
        facet["work_title"]
        for facet in sorted(work_title_facets, key=lambda facet: facet["first_id"])
    ]
    series_ink_classes = _series_ink_classes(palette_titles)

    item_rows = [_collection_item_row(item, series_ink_classes) for item in page_obj.object_list]

    # --- 쿼리스트링 도우미 --------------------------------------------------
    # 서로 다른 네 가지 축 부분집합이라 헷갈리기 쉽다:
    #   chip_query_suffix  — q + 필터 3개 + view. is_wanted/duplicate/
    #                        tradeable/owned는 제외(이들은 칩이 서로
    #                        전환하는 하나의 배타적 서브탭 축이라, 칩이
    #                        이미 활성인 서브탭을 함께 실어 보내면 안 된다)
    #   pager_query        — 필터 3개 + q + view + 서브탭 값 전부(페이징은
    #                        활성 필터에 아무 영향도 주지 않는다)
    #   clear_query_suffix — 필터 3개 + view + 서브탭 값 전부, q는 제외
    #                        (초기화는 검색어만 지운다)
    filter_parts = []
    if work_title:
        filter_parts.append(("work_title", work_title))
    if character_name:
        filter_parts.append(("character_name", character_name))
    if item_type:
        filter_parts.append(("item_type", item_type))

    sub_tab_parts = []
    if is_wanted_value:
        sub_tab_parts.append(("is_wanted", is_wanted_value))
    if duplicate_value:
        sub_tab_parts.append(("duplicate", duplicate_value))
    if tradeable_value:
        sub_tab_parts.append(("tradeable", tradeable_value))
    if owned_value:
        sub_tab_parts.append(("owned", owned_value))

    view_parts = [("view", "list")] if view_mode == "list" else []

    chip_parts = list(filter_parts)
    if q:
        chip_parts.append(("q", q))
    chip_parts += view_parts
    chip_query_suffix = "&" + urlencode(chip_parts) if chip_parts else ""

    clear_parts = list(filter_parts) + sub_tab_parts + view_parts
    clear_query_suffix = urlencode(clear_parts)

    pager_parts = list(filter_parts) + sub_tab_parts
    if q:
        pager_parts.append(("q", q))
    pager_parts += view_parts
    pager_query = "&" + urlencode(pager_parts) if pager_parts else ""

    return _render_archive_list(
        request,
        full_template="core/archive/collection.html",
        fragment_template="core/partials/_archive_results_collection.html",
        context={
            "item_rows": item_rows,
            "page_obj": page_obj,
            "has_items": has_items,
            "owned_count": summary_counts["owned_count"],
            "wanted_count": summary_counts["wanted_count"],
            "tradeable_count": summary_counts["tradeable_count"],
            # 카드가 쓰는 것과 같은 series_ink_classes 맵(위에서 컬렉션
            # 전체로 한 번만 만든 것)을 쓰므로, 사이드바 점과 그것이
            # 필터링하는 카드가 구조적으로 항상 같은 색을 갖는다 — 그게
            # 시리즈별 색상 부여의 핵심이다. work_title_facets는 쿼리
            # 레이어가 이미 개수 내림차순으로 정렬해뒀으므로 여기서는
            # 표시 색만 붙이고 다시 정렬하지 않는다.
            "work_title_counts": [
                {
                    "title": facet["work_title"],
                    "count": facet["count"],
                    "series_ink_class": series_ink_classes.get(facet["work_title"], "gi-0"),
                }
                for facet in work_title_facets
            ],
            "filter_values": user_collection_item_filter_values(user),
            "q": q,
            "has_query": bool(q),
            "work_title": work_title,
            "character_name": character_name,
            "item_type": item_type,
            "is_wanted_value": is_wanted_value,
            "duplicate_value": duplicate_value,
            "tradeable_value": tradeable_value,
            "owned_value": owned_value,
            "view_mode": view_mode,
            "chip_query_suffix": chip_query_suffix,
            "pager_query": pager_query,
            "clear_query_suffix": clear_query_suffix,
        },
    )


def _visit_record_option(record):
    """선택 가능하거나 미리 선택된 방문 기록 하나의 표시 옵션.

    ``label``은 방문 대상의 제목과 날짜를 함께 붙여서, 같은 대상을 두 번
    이상 방문한 경우에도(재방문은 허용되므로 제목만으로는 겹칠 수 있다)
    작성 폼의 드롭다운/잠긴 표시가 명확히 읽히게 한다.
    """
    subject = _subject_view(record)
    return {"id": record.pk, "label": f"{subject['title']} · {record.visited_on}"}


def _parse_collection_visit_preselect(request):
    """컬렉션 항목 작성 폼을 위해, 선택적인 ?visit_record=<id>를 잠긴
    방문 기록으로 해석한다.

    id가 안전한 pk 문자열인지 거르는 것은 _parse_visit_preselect와 동일하지만,
    조회 범위를 요청자가 소유한 VisitRecord 행으로 한정한다 — id는 존재해도
    다른 사용자 소유라면 그 기록을 잠가서는 안 된다. 유효하지 않거나 없거나
    남의 id면 모두 None을 반환해 작성 폼이 선택 드롭다운으로 대체된다.
    """
    ident = request.GET.get("visit_record", "")
    if not is_safe_pk_string(ident):
        return None
    pk = int(ident)
    record = (
        VisitRecord.objects.filter(pk=pk, user=request.user)
        .select_related("event", "personal_entry")
        .first()
    )
    if record is None:
        return None
    return _visit_record_option(record)


@login_required
@ensure_csrf_cookie
def archive_collection_item_create(request):
    """렌더링만 하는 뷰다: 폼은 컬렉션 JS 모듈에서 기존 컬렉션 항목 JSON
    API(archive.collection_urls)로 제출된다. event는 여기서 사용자가
    직접 다루는 컨트롤이 아니다 — create_collection_item이 항상 서버
    쪽에서 visit_record로부터 동기화하므로(FK 쌍 불변식), 이 페이지는
    name="event" input을 절대 렌더링하면 안 된다.
    """
    # 폼을 렌더링할 때마다 한 번씩 발급해 숨은 input에 담는다 — 이 토큰이
    # bfcache DOM 스냅샷에서도 살아남아 재전송 방지용 멱등 키로 쓰인다.
    return render(
        request,
        "core/archive/collection_create.html",
        {
            "selectable_visit_records": list_user_visit_records(request.user),
            "preselect": _parse_collection_visit_preselect(request),
            "COLLECTION_ITEM_TYPE": COLLECTION_ITEM_TYPE,
            "client_token": uuid.uuid4(),
        },
    )


@login_required
@ensure_csrf_cookie
def archive_collection_item_edit(request, item_id):
    """소유자 한정 수정 페이지(다른 사용자의 항목이면 404).
    archive_collection_item_create와 동일하게 name="event" 컨트롤이
    없고(event는 계속 서버가 visit_record로 동기화한다) 공개 범위
    컨트롤도 없다(향후 교환 옵트인 게이트를 위해 남겨둔 자리).
    """
    item = get_object_or_404(CollectionItem, pk=item_id, user=request.user)
    return render(
        request,
        "core/archive/collection_edit.html",
        {
            "item": item,
            "COLLECTION_ITEM_TYPE": COLLECTION_ITEM_TYPE,
        },
    )


def _collection_item_meta_rows(item):
    """읽기 전용 상세 페이지용 파생 메타 정보 행들.

    각 행은 뒷받침하는 필드가 비어 있으면 생략된다 — 호출하는 템플릿은
    이 리스트가 비어 있지 않을 때만 전체 ``<dl>``을 렌더링한다. 연결된
    방문 행의 제목은 방문의 Event 제목을 우선하고, 방문에 Event가 없으면
    PersonalEntry 제목으로 대체한다(collection_edit.html:115의 기존
    분기와 동일).
    """
    rows = []
    if item.quantity > 0:
        rows.append(
            {"label": "수량", "value": f"{item.quantity}개", "url": None, "lock_hint": False}
        )
    if item.tradeable_quantity > 0:
        rows.append(
            {
                "label": "교환 가능",
                "value": f"{item.tradeable_quantity}개",
                "url": None,
                "lock_hint": False,
            }
        )
    if item.acquired_on:
        rows.append(
            {
                "label": "획득일",
                "value": item.acquired_on.strftime("%Y.%m.%d"),
                "url": None,
                "lock_hint": False,
            }
        )
    if item.acquisition_source:
        rows.append(
            {
                "label": "획득 경로",
                "value": item.acquisition_source,
                "url": None,
                "lock_hint": False,
            }
        )
    visit = item.visit_record
    if visit is not None:
        title = visit.event.title if visit.event else visit.personal_entry.title
        rows.append(
            {
                "label": "연결된 방문 기록",
                "value": f"{title} · {visit.visited_on:%m-%d}",
                "url": f"/archive/visits/{visit.pk}/",
                "lock_hint": True,
            }
        )
    return rows


@login_required
@ensure_csrf_cookie
def archive_collection_item_detail(request, item_id):
    """CollectionItem 하나의 읽기 전용 상세 페이지(소유자 한정).

    항목 하나만을 위한 팔레트를 따로 계산하지 않고
    archive_collection_items와 컬렉션 전체 색상 팔레트를 공유한다
    (user_collection_item_work_title_facets를 first_id로 정렬해 구성) —
    사용자가 목록을 보든 항목 하나의 상세를 보든 work_title의 색 버킷은
    반드시 같아야 한다.
    """
    item = get_object_or_404(
        CollectionItem.objects.select_related(
            "visit_record__event", "visit_record__personal_entry"
        ),
        pk=item_id,
        user=request.user,
    )
    work_title_facets = user_collection_item_work_title_facets(request.user)
    palette_titles = [
        facet["work_title"]
        for facet in sorted(work_title_facets, key=lambda facet: facet["first_id"])
    ]
    series_ink_classes = _series_ink_classes(palette_titles)
    return render(
        request,
        "core/archive/collection_detail.html",
        {
            "item": item,
            "row": _collection_item_row(item, series_ink_classes),
            "meta_rows": _collection_item_meta_rows(item),
            "tradeable_quantity": item.tradeable_quantity,
        },
    )
