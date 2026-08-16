from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import (
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
    inline_serializer,
)
from rest_framework import serializers, status
from rest_framework.generics import ListCreateAPIView, RetrieveDestroyAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from .models import (
    CollectionItem,
    EventInterest,
    PersonalEntry,
    UserEventStatus,
    VisitRecord,
    VisitRecordPhoto,
)
from .queries import list_user_collection_items, list_user_personal_entries
from .serializers import (
    CollectionItemQuerySerializer,
    CollectionItemSerializer,
    CollectionItemUpdateSerializer,
    EventInterestSerializer,
    PersonalEntrySerializer,
    PersonalEntryUpdateSerializer,
    UserEventStatusQuerySerializer,
    UserEventStatusSerializer,
    UserEventStatusUpdateSerializer,
    VisitRecordPhotoUploadSerializer,
    VisitRecordSerializer,
    VisitRecordUpdateSerializer,
)
from .services import (
    MAX_PHOTOS_PER_RECORD,
    DuplicateEventInterestError,
    DuplicateUserEventStatusError,
    PhotoLimitExceededError,
    VisitRecordExistsError,
    complete_visit_with_record,
    create_collection_item,
    create_event_interest,
    create_personal_entry,
    create_user_event_status,
    create_visit_record_photo,
    mark_missed,
    mark_visited,
    remove_event_interest,
    remove_user_event_status,
    revert_to_planned,
    update_collection_item,
    update_visit_record,
)


def _translate_domain_validation_error(exc):
    """서비스 계층의 django ValidationError를 DRF ValidationError로
    다시 던진다. DRF의 예외 처리기는 django.core.exceptions.ValidationError를
    스스로 변환해 주지 않으므로, 그대로 두면 archive.services의 불변식
    위반(예: CollectionItem 수량/FK 짝 검사)이 처리되지 않은 500으로
    새어 나간다. 이 함수를 거쳐야 400 응답으로 나간다.
    """
    if hasattr(exc, "error_dict"):
        raise ValidationError(exc.message_dict)
    raise ValidationError(exc.messages)


class PersonalEntryPagination(PageNumberPagination):
    page_size = 20


@extend_schema_view(
    get=extend_schema(
        tags=["collection"],
        summary="내 비공식 기록 목록을 조회한다",
        responses={200: PersonalEntrySerializer, 403: OpenApiResponse(description="인증되지 않은 요청.")},
    ),
    post=extend_schema(
        tags=["collection"],
        summary="새 비공식 기록을 생성한다",
        responses={
            201: PersonalEntrySerializer,
            400: OpenApiResponse(description="입력값 검증 실패."),
            403: OpenApiResponse(description="인증되지 않은 요청."),
        },
    ),
)
class PersonalEntryListCreateView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PersonalEntrySerializer
    pagination_class = PersonalEntryPagination
    throttle_scope = "personal_entry_create"

    def get_throttles(self):
        # ScopedRateThrottle은 뷰 전체에 적용되므로 쓰기 경로에만 걸리게
        # 한다 — 생성 폭주 방지가 목록 조회(GET)까지 막으면 안 된다.
        if self.request.method == "POST":
            return [ScopedRateThrottle()]
        return []

    def get_queryset(self):
        return list_user_personal_entries(self.request.user)

    def perform_create(self, serializer):
        # 소유자는 요청자 정보로 정하며 요청 본문 값은 쓰지 않는다
        serializer.instance = create_personal_entry(
            user=self.request.user, **serializer.validated_data
        )


@extend_schema_view(
    get=extend_schema(
        tags=["collection"],
        summary="비공식 기록 상세를 조회한다",
        responses={
            200: PersonalEntrySerializer,
            403: OpenApiResponse(description="인증되지 않은 요청."),
            404: OpenApiResponse(description="존재하지 않거나 소유하지 않은 기록."),
        },
    ),
    patch=extend_schema(
        tags=["collection"],
        summary="비공식 기록을 수정한다",
        responses={
            200: PersonalEntrySerializer,
            400: OpenApiResponse(description="입력값 검증 실패."),
            403: OpenApiResponse(description="인증되지 않은 요청."),
            404: OpenApiResponse(description="존재하지 않거나 소유하지 않은 기록."),
        },
    ),
    delete=extend_schema(
        tags=["collection"],
        summary="비공식 기록을 삭제한다",
        responses={
            204: OpenApiResponse(description="삭제됨."),
            403: OpenApiResponse(description="인증되지 않은 요청."),
            404: OpenApiResponse(description="존재하지 않거나 소유하지 않은 기록."),
        },
    ),
)
class PersonalEntryDetailView(RetrieveUpdateDestroyAPIView):
    http_method_names = ["get", "patch", "delete", "head", "options"]  # 전체교체(PUT) 미허용 — CollectionItemDetailView와 동일 취지
    permission_classes = [IsAuthenticated]
    serializer_class = PersonalEntrySerializer

    def get_queryset(self):
        return PersonalEntry.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return PersonalEntryUpdateSerializer
        return PersonalEntrySerializer


class EventInterestPagination(PageNumberPagination):
    page_size = 20


@extend_schema_view(
    get=extend_schema(
        tags=["archive"],
        summary="내 관심 행사 목록을 조회한다",
        responses={200: EventInterestSerializer, 403: OpenApiResponse(description="인증되지 않은 요청.")},
    ),
    post=extend_schema(
        tags=["archive"],
        summary="행사를 관심으로 등록한다",
        responses={
            201: EventInterestSerializer,
            400: OpenApiResponse(description="입력값 검증 실패."),
            403: OpenApiResponse(description="인증되지 않은 요청."),
            409: OpenApiResponse(description="이미 관심으로 등록된 행사."),
        },
    ),
)
class EventInterestListCreateView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = EventInterestSerializer
    pagination_class = EventInterestPagination
    throttle_scope = "event_interest_create"

    def get_throttles(self):
        # ScopedRateThrottle은 뷰 전체에 적용되므로 쓰기 경로에만 걸리게
        # 한다 — 생성 폭주 방지가 목록 조회(GET)까지 막으면 안 된다.
        if self.request.method == "POST":
            return [ScopedRateThrottle()]
        return []

    def get_queryset(self):
        return EventInterest.objects.filter(user=self.request.user).order_by("-id")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            interest = create_event_interest(
                user=request.user,
                event=serializer.validated_data.get("event"),
                personal_entry=serializer.validated_data.get("personal_entry"),
            )
        except DuplicateEventInterestError:
            return Response(
                {
                    "code": "duplicate_event_interest",
                    "detail": "Event interest already exists for this event.",
                },
                status=status.HTTP_409_CONFLICT,
            )
        response_serializer = self.get_serializer(interest)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(
        tags=["archive"],
        summary="관심 행사 상세를 조회한다",
        responses={
            200: EventInterestSerializer,
            403: OpenApiResponse(description="인증되지 않은 요청."),
            404: OpenApiResponse(description="존재하지 않거나 소유하지 않은 관심 행사."),
        },
    ),
    delete=extend_schema(
        tags=["archive"],
        summary="관심 행사를 해제한다",
        responses={
            204: OpenApiResponse(description="삭제됨."),
            403: OpenApiResponse(description="인증되지 않은 요청."),
            404: OpenApiResponse(description="존재하지 않거나 소유하지 않은 관심 행사."),
        },
    ),
)
class EventInterestDetailView(RetrieveDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = EventInterestSerializer

    def get_queryset(self):
        return EventInterest.objects.filter(user=self.request.user)

    def perform_destroy(self, instance):
        remove_event_interest(interest=instance)


class UserEventStatusPagination(PageNumberPagination):
    page_size = 20


@extend_schema_view(
    get=extend_schema(
        tags=["archive"],
        summary="내 행사 상태 목록을 조회한다",
        responses={
            200: UserEventStatusSerializer,
            400: OpenApiResponse(description="쿼리 파라미터가 유효하지 않다."),
            403: OpenApiResponse(description="인증되지 않은 요청."),
        },
    ),
    post=extend_schema(
        tags=["archive"],
        summary="행사 상태를 등록한다",
        responses={
            201: UserEventStatusSerializer,
            400: OpenApiResponse(description="입력값 검증 실패, 또는 이미 방문 기록이 있는 상태 전환."),
            403: OpenApiResponse(description="인증되지 않은 요청."),
            409: OpenApiResponse(description="이미 등록된 행사 상태."),
        },
    ),
)
class UserEventStatusListCreateView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = UserEventStatusSerializer
    pagination_class = UserEventStatusPagination
    throttle_scope = "user_event_status_create"

    def get_throttles(self):
        # ScopedRateThrottle은 뷰 전체에 적용되므로 쓰기 경로에만 걸리게
        # 한다 — 생성 폭주 방지가 목록 조회(GET)까지 막으면 안 된다.
        if self.request.method == "POST":
            return [ScopedRateThrottle()]
        return []

    def _validated_query_params(self):
        serializer = UserEventStatusQuerySerializer(data=self.request.query_params)
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def get_queryset(self):
        params = self._validated_query_params()
        queryset = UserEventStatus.objects.filter(user=self.request.user)
        if "event" in params:
            queryset = queryset.filter(event_id=params["event"])
        if "status" in params:
            queryset = queryset.filter(status=params["status"])
        return queryset.order_by("id")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            status_object = create_user_event_status(
                user=request.user,
                event=serializer.validated_data.get("event"),
                personal_entry=serializer.validated_data.get("personal_entry"),
                status=serializer.validated_data["status"],
            )
        except DuplicateUserEventStatusError:
            return Response(
                {
                    "code": "duplicate_user_event_status",
                    "detail": "User event status already exists for this event.",
                },
                status=status.HTTP_409_CONFLICT,
            )
        except VisitRecordExistsError:
            raise ValidationError(
                {"status": "이미 방문 기록이 있는 항목은 이 상태로 등록할 수 없습니다."}
            )
        response_serializer = self.get_serializer(status_object)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(
        tags=["archive"],
        summary="행사 상태 상세를 조회한다",
        responses={
            200: UserEventStatusSerializer,
            403: OpenApiResponse(description="인증되지 않은 요청."),
            404: OpenApiResponse(description="존재하지 않거나 소유하지 않은 행사 상태."),
        },
    ),
    patch=extend_schema(
        tags=["archive"],
        summary="행사 상태를 전환한다",
        responses={
            200: UserEventStatusSerializer,
            400: OpenApiResponse(description="이미 방문 기록이 있는 항목은 이 상태로 되돌릴 수 없다."),
            403: OpenApiResponse(description="인증되지 않은 요청."),
            404: OpenApiResponse(description="존재하지 않거나 소유하지 않은 행사 상태."),
        },
    ),
    delete=extend_schema(
        tags=["archive"],
        summary="행사 상태를 삭제한다",
        responses={
            204: OpenApiResponse(description="삭제됨."),
            403: OpenApiResponse(description="인증되지 않은 요청."),
            404: OpenApiResponse(description="존재하지 않거나 소유하지 않은 행사 상태."),
        },
    ),
)
class UserEventStatusDetailView(RetrieveUpdateDestroyAPIView):
    http_method_names = ["get", "patch", "delete", "head", "options"]
    permission_classes = [IsAuthenticated]

    # 목표 상태마다 별도의 전환 규칙이 있다(방문/놓침은 옵트아웃 플래그를
    # 그대로 두고, 예정은 다시 고정한다). 이렇게 라우팅해야 상태 전환
    # 규칙이 서비스 계층에 남고, 무조건적인 serializer.save()로 흘러가지
    # 않는다.
    _TRANSITIONS = {
        UserEventStatus.Status.VISITED: mark_visited,
        UserEventStatus.Status.MISSED: mark_missed,
        UserEventStatus.Status.PLANNED: revert_to_planned,
    }

    def get_queryset(self):
        return UserEventStatus.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return UserEventStatusUpdateSerializer
        return UserEventStatusSerializer

    def perform_update(self, serializer):
        target = serializer.validated_data.get("status")
        transition = self._TRANSITIONS.get(target)
        if transition is None:
            serializer.save()
            return
        try:
            transition(user_event_status=serializer.instance)
        except VisitRecordExistsError:
            raise ValidationError(
                {"status": "이미 방문 기록이 있는 항목은 이 상태로 되돌릴 수 없습니다."}
            )

    def perform_destroy(self, instance):
        remove_user_event_status(user_event_status=instance)


class VisitRecordPagination(PageNumberPagination):
    page_size = 20


@extend_schema_view(
    get=extend_schema(
        tags=["archive"],
        summary="내 다녀온 기록 목록을 조회한다",
        responses={200: VisitRecordSerializer, 403: OpenApiResponse(description="인증되지 않은 요청.")},
    ),
    post=extend_schema(
        tags=["archive"],
        summary="다녀온 기록을 생성한다",
        responses={
            201: VisitRecordSerializer,
            400: OpenApiResponse(description="입력값 검증 실패."),
            403: OpenApiResponse(description="인증되지 않은 요청."),
        },
    ),
)
class VisitRecordListCreateView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = VisitRecordSerializer
    pagination_class = VisitRecordPagination
    throttle_scope = "visit_record_create"

    def get_throttles(self):
        # ScopedRateThrottle은 뷰 전체에 적용되므로 쓰기 경로에만 걸리게
        # 한다 — 생성 폭주 방지가 목록 조회(GET)까지 막으면 안 된다.
        if self.request.method == "POST":
            return [ScopedRateThrottle()]
        return []

    def get_queryset(self):
        return (
            VisitRecord.objects.filter(user=self.request.user)
            .order_by("-visited_on", "-id")
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        record = complete_visit_with_record(
            user=request.user,
            event=serializer.validated_data.get("event"),
            personal_entry=serializer.validated_data.get("personal_entry"),
            visited_on=serializer.validated_data["visited_on"],
            short_review=serializer.validated_data.get("short_review", ""),
            client_token=serializer.validated_data.get("client_token"),
        )
        response_serializer = self.get_serializer(record)
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)


@extend_schema_view(
    get=extend_schema(
        tags=["archive"],
        summary="다녀온 기록 상세를 조회한다",
        responses={
            200: VisitRecordSerializer,
            403: OpenApiResponse(description="인증되지 않은 요청."),
            404: OpenApiResponse(description="존재하지 않거나 소유하지 않은 기록."),
        },
    ),
    patch=extend_schema(
        tags=["archive"],
        summary="다녀온 기록을 수정한다",
        responses={
            200: VisitRecordSerializer,
            400: OpenApiResponse(description="입력값 검증 실패."),
            403: OpenApiResponse(description="인증되지 않은 요청."),
            404: OpenApiResponse(description="존재하지 않거나 소유하지 않은 기록."),
        },
    ),
    delete=extend_schema(
        tags=["archive"],
        summary="다녀온 기록을 삭제한다",
        responses={
            204: OpenApiResponse(description="삭제됨."),
            403: OpenApiResponse(description="인증되지 않은 요청."),
            404: OpenApiResponse(description="존재하지 않거나 소유하지 않은 기록."),
        },
    ),
)
class VisitRecordDetailView(RetrieveUpdateDestroyAPIView):
    http_method_names = ["get", "patch", "delete", "head", "options"]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return VisitRecord.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return VisitRecordUpdateSerializer
        return VisitRecordSerializer

    def perform_update(self, serializer):
        record = serializer.instance
        update_visit_record(
            record=record,
            visited_on=serializer.validated_data.get("visited_on", record.visited_on),
            short_review=serializer.validated_data.get(
                "short_review", record.short_review
            ),
        )


class VisitRecordPhotoCreateView(APIView):
    permission_classes = [IsAuthenticated]
    # 이 뷰는 POST만 구현하므로(GET 없음) 메서드로 분기할 필요 없이
    # 스로틀을 그냥 붙인다.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "visit_record_photo_create"

    @extend_schema(
        tags=["archive"],
        summary="다녀온 기록에 사진을 첨부한다",
        request=VisitRecordPhotoUploadSerializer,
        responses={
            201: inline_serializer(
                "VisitRecordPhotoCreateResponse",
                {
                    "id": serializers.IntegerField(),
                    "visit_record": serializers.IntegerField(),
                },
            ),
            400: OpenApiResponse(
                description=f"입력값 검증 실패, 또는 기록당 사진이 {MAX_PHOTOS_PER_RECORD}장을 초과함."
            ),
            403: OpenApiResponse(description="인증되지 않은 요청."),
            404: OpenApiResponse(description="존재하지 않거나 소유하지 않은 다녀온 기록."),
        },
    )
    def post(self, request, record_id):
        record = get_object_or_404(VisitRecord, pk=record_id, user=request.user)
        serializer = VisitRecordPhotoUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            photo = create_visit_record_photo(
                visit_record=record, **serializer.validated_data
            )
        except PhotoLimitExceededError:
            return Response(
                {
                    "code": "photo_limit_exceeded",
                    "detail": f"A visit record can have at most {MAX_PHOTOS_PER_RECORD} photos.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        except VisitRecord.DoesNotExist:
            # 위 소유권 확인 시점엔 기록이 있었지만, 서비스의
            # select_for_update().get(...)이 실행되기 전에(예: 동시
            # 요청으로) 삭제된 경우다. 500이 아니라 평범한 404로 보여준다.
            raise Http404
        return Response({"id": photo.id, "visit_record": record.id}, status=status.HTTP_201_CREATED)


class VisitRecordPhotoDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["archive"],
        summary="다녀온 기록에 첨부된 사진을 삭제한다",
        responses={
            204: OpenApiResponse(description="삭제됨."),
            403: OpenApiResponse(description="인증되지 않은 요청."),
            404: OpenApiResponse(description="존재하지 않거나 소유하지 않은 사진."),
        },
    )
    def delete(self, request, record_id, photo_id):
        photo = get_object_or_404(
            VisitRecordPhoto.objects.select_related("visit_record"),
            pk=photo_id,
            visit_record_id=record_id,
            visit_record__user=request.user,
        )
        photo.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CollectionItemPagination(PageNumberPagination):
    page_size = 20


@extend_schema_view(
    get=extend_schema(
        tags=["collection"],
        summary="내 굿즈 컬렉션 목록을 조회한다",
        responses={
            200: CollectionItemSerializer,
            400: OpenApiResponse(description="쿼리 파라미터가 유효하지 않다."),
            403: OpenApiResponse(description="인증되지 않은 요청."),
        },
    ),
    post=extend_schema(
        tags=["collection"],
        summary="굿즈 컬렉션 항목을 생성한다",
        responses={
            201: CollectionItemSerializer,
            400: OpenApiResponse(description="입력값 검증 실패(예: 교환 가능 수량이 보유 수량을 초과)."),
            403: OpenApiResponse(description="인증되지 않은 요청."),
        },
    ),
)
class CollectionItemListCreateView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = CollectionItemSerializer
    pagination_class = CollectionItemPagination
    throttle_scope = "collection_item_create"

    def get_throttles(self):
        # ScopedRateThrottle은 뷰 전체에 적용되므로 쓰기 경로에만 걸리게
        # 한다 — 생성 폭주 방지가 목록 조회(GET)까지 막으면 안 된다.
        if self.request.method == "POST":
            return [ScopedRateThrottle()]
        return []

    def _validated_query_params(self):
        # .dict()로 변환하는 이유: QueryDict을 그대로 넘기면 DRF의
        # BooleanField가 HTML 폼 제출로 오인해, 값이 없는 선택적
        # BooleanField를 건너뛰지 않고 조용히 False로 취급한다. 그러면
        # 지정하지 않은 is_wanted/duplicate/tradeable 필터가 결과를
        # 잘못 좁혀버린다.
        serializer = CollectionItemQuerySerializer(data=self.request.query_params.dict())
        serializer.is_valid(raise_exception=True)
        return serializer.validated_data

    def get_queryset(self):
        return list_user_collection_items(self.request.user, **self._validated_query_params())

    def perform_create(self, serializer):
        # 소유자는 요청자 정보로 정하며 요청 본문 값은 쓰지 않는다
        try:
            serializer.instance = create_collection_item(
                user=self.request.user, **serializer.validated_data
            )
        except DjangoValidationError as exc:
            _translate_domain_validation_error(exc)


@extend_schema_view(
    get=extend_schema(
        tags=["collection"],
        summary="굿즈 컬렉션 항목 상세를 조회한다",
        responses={
            200: CollectionItemSerializer,
            403: OpenApiResponse(description="인증되지 않은 요청."),
            404: OpenApiResponse(description="존재하지 않거나 소유하지 않은 항목."),
        },
    ),
    patch=extend_schema(
        tags=["collection"],
        summary="굿즈 컬렉션 항목을 수정한다",
        responses={
            200: CollectionItemSerializer,
            400: OpenApiResponse(description="입력값 검증 실패(예: 교환 가능 수량이 보유 수량을 초과)."),
            403: OpenApiResponse(description="인증되지 않은 요청."),
            404: OpenApiResponse(description="존재하지 않거나 소유하지 않은 항목."),
        },
    ),
    delete=extend_schema(
        tags=["collection"],
        summary="굿즈 컬렉션 항목을 삭제한다",
        responses={
            204: OpenApiResponse(description="삭제됨."),
            403: OpenApiResponse(description="인증되지 않은 요청."),
            404: OpenApiResponse(description="존재하지 않거나 소유하지 않은 항목."),
        },
    ),
)
class CollectionItemDetailView(RetrieveUpdateDestroyAPIView):
    http_method_names = ["get", "patch", "delete", "head", "options"]
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return CollectionItem.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.request.method == "PATCH":
            return CollectionItemUpdateSerializer
        return CollectionItemSerializer

    def perform_update(self, serializer):
        # update_collection_item은 select_for_update()로 자기 행을
        # 다시 조회해서 그 최신 인스턴스를 반환하며, serializer.instance를
        # 직접 수정하지 않는다 — 응답은 반드시 이 반환값으로 구성해야
        # 한다.
        try:
            serializer.instance = update_collection_item(
                item=serializer.instance, **serializer.validated_data
            )
        except DjangoValidationError as exc:
            _translate_domain_validation_error(exc)
        except CollectionItem.DoesNotExist:
            # 이 뷰의 get_object() 확인 시점엔 항목이 있었지만, 서비스의
            # select_for_update().get(...)이 실행되기 전에(예: 동시 요청
            # 으로) 삭제된 경우다 — VisitRecordPhotoCreateView가
            # VisitRecord에 대해 이미 막고 있는 것과 같은 TOCTOU 틈이다.
            # 500이 아니라 평범한 404로 보여준다.
            raise Http404
