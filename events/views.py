from rest_framework.authentication import SessionAuthentication
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from django.shortcuts import get_object_or_404

from core.analytics import record_event
from core.models import AnalyticsEvent

from .models import Event
from .queries import PUBLIC_LISTING_PAGE_SIZE, list_published_events, parse_public_listing_params
from .serializers import EventPosterUploadSerializer, EventSerializer
from .services import clear_event_poster, set_event_poster


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


class EventPosterView(APIView):
    """스태프 전용: 이벤트 포스터 이미지를 업로드/삭제한다.

    인증을 SessionAuthentication으로 못박아 BasicAuth가 CSRF 보호를 우회하지 못하게 한다.
    전역 DRF 설정(config/settings.py)이 이미 같은 값을 쓰지만, 관리자 전용 엔드포인트가
    전역 설정 변경에 조용히 휩쓸리지 않도록 여기서도 명시적으로 고정한다.
    """

    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        event = get_object_or_404(Event.objects.published(), pk=pk)
        serializer = EventPosterUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        set_event_poster(event=event, image=serializer.validated_data["image"])
        return Response({"poster_url": event.poster_image.url})

    def delete(self, request, pk):
        event = get_object_or_404(Event.objects.published(), pk=pk)
        clear_event_poster(event=event)
        return Response(status=204)
