"""이벤트 조회 공용 레이어. JSON API(events/views.py)와 SSR 화면(core/views.py)이
필터·정렬 로직을 중복 구현하지 않고 함께 쓴다."""
from datetime import timedelta

from django.db import models
from django.utils import timezone

from .models import Event
from .serializers import EventQuerySerializer

PUBLIC_LISTING_PAGE_SIZE = 10

# 같은 키를 여러 번 넣으면(?region=a&region=b) OR로 묶어 필터링하는 항목.
MULTI_VALUE_FIELDS = ("region", "category")


def _collect_values(raw_params, key):
    """key에 해당하는 빈 값 아닌 값들을 리스트로 반환한다.

    getlist()가 있으면(DRF query_params / QueryDict) 반복 파라미터를 모두 살리고,
    없으면 단일 값으로 처리한다.
    """
    getlist = getattr(raw_params, "getlist", None)
    values = getlist(key) if callable(getlist) else [raw_params.get(key)]
    return [value for value in values if value not in (None, "")]


def parse_public_listing_params(raw_params):
    """공개 목록 쿼리 파라미터를 파싱·검증한다. DRF query_params와 Django GET 둘 다 받는다.

    "전체" 같은 빈 값 필터는 여기서 걸러내야, 브라우즈 폼이 항상 submit하는
    빈 선택지가 ChoiceField/DateField 검증에서 오류로 튀지 않고 "필터 없음"으로 처리된다.
    """
    allowed_fields = EventQuerySerializer().fields
    data = {}
    for key in allowed_fields:
        if key in MULTI_VALUE_FIELDS:
            values = _collect_values(raw_params, key)
            if values:
                data[key] = values
        else:
            value = raw_params.get(key)
            if value not in (None, ""):
                data[key] = value

    serializer = EventQuerySerializer(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def list_published_events(params, *, today=None):
    """params로 필터링한 게시된 이벤트를 정렬해 반환한다. today는 테스트용 날짜 오버라이드."""
    if today is None:
        today = timezone.localdate()
    return (
        Event.objects.published()
        .filter_for_public_listing(params, today=today)
        .order_for_public_listing(today=today, sort=params.get("sort"))
    )


def list_published_events_for_month(params, *, year, month, today=None):
    """이벤트 달력(이중 달력 설계 §6)용: 해당 (year, month)와 겹치는 게시 이벤트를,
    list_published_events와 같은 필터·정렬에 월 겹침 조건만 추가해 반환한다.
    """
    if today is None:
        today = timezone.localdate()
    return (
        Event.objects.published()
        .overlapping_month(year, month)
        .filter_for_public_listing(params, today=today)
        .order_for_public_listing(today=today, sort=params.get("sort"))
    )


# 각 _*_qs() 헬퍼가 경고 하나의 조건을 담는 단일 소스다. count_published_*는 여기에
# count()만 씌우고, list_staff_events()도 같은 쿼리셋을 재사용해 대시보드 집계 수와
# 드릴다운 목록이 항상 같은 집합을 가리키게 한다.


def _missing_official_url_qs():
    return Event.objects.published().filter(models.Q(official_url__isnull=True) | models.Q(official_url=""))


def _ended_still_published_qs(*, today=None):
    if today is None:
        today = timezone.localdate()
    return Event.objects.published().filter(end_date__lt=today)


def _missing_poster_qs():
    return Event.objects.published().filter(models.Q(poster_image__isnull=True) | models.Q(poster_image=""))


def _missing_dates_qs():
    return Event.objects.published().filter(models.Q(start_date__isnull=True) | models.Q(end_date__isnull=True))


def _missing_region_qs():
    """region이 정확히 빈 문자열인 게시 이벤트. 공백만 있는 값(" ")은 일부러 정규화하지 않아 여기 안 걸린다."""
    return Event.objects.published().filter(region="")


def _needs_reverification_qs(*, today=None):
    """시작 임박 또는 진행 중이면서 한 번도 검증되지 않았거나, D-7 기준(시작일-7일)보다
    먼저 마지막 검증된 게시 이벤트.

    시작일·종료일이 없는 이벤트는 SQL에서 NULL 비교가 자동으로 걸러줘서, 그 결손은
    missing_dates 경고 하나에서만 세고 여기서 중복 집계하지 않는다.
    """
    if today is None:
        today = timezone.localdate()
    reverify_deadline = models.ExpressionWrapper(
        models.F("start_date") - timedelta(days=7),
        output_field=models.DateField(),
    )
    return (
        Event.objects.published()
        .annotate(reverify_deadline=reverify_deadline)
        .filter(end_date__gte=today, reverify_deadline__lte=today)
        .filter(
            models.Q(verified_at__isnull=True)
            | models.Q(verified_at__date__lt=models.F("reverify_deadline"))
        )
    )


def count_published_missing_official_url() -> int:
    """official_url이 없는(NULL 또는 빈 값) 게시 이벤트 수."""
    return _missing_official_url_qs().count()


def count_published_ended_still_published(*, today=None) -> int:
    """종료일이 오늘보다 지난 게시 이벤트 수. 종료일 없는 이벤트는 "종료"로 안 친다."""
    return _ended_still_published_qs(today=today).count()


def count_published_missing_poster() -> int:
    """포스터 이미지가 없는 게시 이벤트 수."""
    return _missing_poster_qs().count()


def count_published_missing_dates() -> int:
    """시작일 또는 종료일이 없는 게시 이벤트 수(둘 다 없어도 한 번만 센다)."""
    return _missing_dates_qs().count()


def count_published_missing_region() -> int:
    """region이 정확히 빈 문자열인 게시 이벤트 수."""
    return _missing_region_qs().count()


def count_published_needs_reverification(*, today=None) -> int:
    """D-7 재검증이 필요한 게시 이벤트 수. 조건은 _needs_reverification_qs 참고."""
    return _needs_reverification_qs(today=today).count()


def published_quality_warnings(*, today=None) -> dict:
    """스태프 대시보드용 품질 경고 집계를 dict로 반환한다.

    "total"은 needs_reverification을 뺀 5개 경고 카운트의 합이다. 대시보드 표가
    그 5행만 보여주므로 "표의 합 == total"이 유지되도록 일부러 뺐다. 이벤트 하나가
    5개 중 2개에 걸리면 total에 2로 반영된다(중복 이벤트 수가 아니라 경고 트립 수).
    """
    missing_official_url = count_published_missing_official_url()
    ended_still_published = count_published_ended_still_published(today=today)
    missing_poster = count_published_missing_poster()
    missing_dates = count_published_missing_dates()
    missing_region = count_published_missing_region()
    needs_reverification = count_published_needs_reverification(today=today)
    return {
        "missing_official_url": missing_official_url,
        "ended_still_published": ended_still_published,
        "missing_poster": missing_poster,
        "missing_dates": missing_dates,
        "missing_region": missing_region,
        "needs_reverification": needs_reverification,
        "total": (
            missing_official_url
            + ended_still_published
            + missing_poster
            + missing_dates
            + missing_region
        ),
    }


QUALITY_WARNING_KEYS = (
    "missing_official_url",
    "ended_still_published",
    "missing_poster",
    "missing_dates",
    "missing_region",
    "needs_reverification",
)

STAFF_EVENT_LISTING_PAGE_SIZE = 15

_NON_DATED_WARNING_QUERYSETS = {
    "missing_official_url": _missing_official_url_qs,
    "missing_poster": _missing_poster_qs,
    "missing_dates": _missing_dates_qs,
    "missing_region": _missing_region_qs,
}


def list_staff_events(*, warning=None, publish_status=None, today=None, search=""):
    """스태프 이벤트 콘솔용 목록을 created_at 최신순으로 반환한다.

    warning은 count_published_*가 세는 것과 같은 쿼리셋으로 좁힌다(드릴다운 일치).
    알 수 없는 warning/publish_status 값은 querystring 오류로 보지 않고 조용히 무시한다.
    search는 표에 보이는 세 열(행사명·작품명·장소)을 함께 본다.
    """
    if warning == "ended_still_published":
        queryset = _ended_still_published_qs(today=today)
    elif warning == "needs_reverification":
        queryset = _needs_reverification_qs(today=today)
    elif warning in _NON_DATED_WARNING_QUERYSETS:
        queryset = _NON_DATED_WARNING_QUERYSETS[warning]()
    else:
        queryset = Event.objects.all()

    if publish_status in Event.PublishStatus.values:
        queryset = queryset.filter(publish_status=publish_status)

    term = search.strip()
    if term:
        queryset = queryset.filter(
            models.Q(title__icontains=term)
            | models.Q(work_title__icontains=term)
            | models.Q(location_name__icontains=term)
        )

    return queryset.order_by("-created_at")
