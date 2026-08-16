from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination

from core.analytics import record_event
from core.models import AnalyticsEvent

from .models import Event
from .queries import PUBLIC_LISTING_PAGE_SIZE, list_published_events, parse_public_listing_params
from .serializers import EventSerializer


class EventPagination(PageNumberPagination):
    page_size = PUBLIC_LISTING_PAGE_SIZE


class PublicEventListView(ListAPIView):
    serializer_class = EventSerializer
    pagination_class = EventPagination

    def get_queryset(self):
        params = parse_public_listing_params(self.request.query_params)
        # q가 있으면 검색, 없으면 단순 열람으로 보고 둘 중 하나만 요청당 한 번 기록한다.
        event_name = (
            AnalyticsEvent.EventName.EVENT_SEARCHED
            if params.get("q")
            else AnalyticsEvent.EventName.EVENT_LIST_VIEWED
        )
        # swagger_fake_view: drf-spectacular가 스키마 생성 시 내성 검사용으로
        # 뷰에 세팅하는 속성이다 — 그 동안은 실제 요청이 아니므로 분석 기록을 건너뛴다.
        if not getattr(self, "swagger_fake_view", False):
            record_event(event_name=event_name, user=self.request.user)
        return list_published_events(params)


class PublicEventDetailView(RetrieveAPIView):
    serializer_class = EventSerializer

    def get_queryset(self):
        return Event.objects.published()

    def retrieve(self, request, *args, **kwargs):
        response = super().retrieve(request, *args, **kwargs)
        record_event(
            event_name=AnalyticsEvent.EventName.EVENT_DETAIL_VIEWED,
            user=request.user,
            target_type="event",
            target_id=response.data["id"],
        )
        return response
