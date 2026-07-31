"""core.analytics — 행동 이벤트 기록.

도메인을 가로지르는 관심사다: events/archive가 `record_event`를 호출해
0단계 행동 이벤트들을 기록하되(AnalyticsEvent.EventName 참고), 이 모듈을
매개로 어느 도메인도 다른 도메인에 의존하지 않는다. `core`는 이미 모든
도메인 앱이 임포트하는 공용 의존 대상이라 새 앱을 만들지 않고 여기 둔다.

프라이버시: `pseudonymous_user_key`는 원본 유저 pk를 복원 가능한 방식으로
저장·유도하지 않는다(아래 독스트링 참고). `record_event`는 개인정보를
담을 수 있는 컨텍스트 키(자유 텍스트, 연락처, 미디어 URL)가 들어오면
바로 실패한다 — FORBIDDEN_CONTEXT_KEYS 참고.
"""
import hashlib
import hmac
import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from core.models import AnalyticsEvent


logger = logging.getLogger(__name__)

# 개인정보를 담을 수 있는 컨텍스트 키(사용자가 입력한 자유 텍스트, 연락처,
# 미디어 URL)는 조용히 저장하지 않고 바로 거부한다 — record_event 참고.
# "name"과 "memo"(컬렉션 항목 자유 텍스트)는 미래 실수 방지용이다:
# 현재 collection_item_* 이벤트를 호출하는 곳은 어디도 컨텍스트를 넘기지
# 않으므로 지금 당장 막고 있는 실제 호출 지점은 없다.
FORBIDDEN_CONTEXT_KEYS = frozenset(
    {"short_review", "note", "email", "photo_url", "image", "name", "memo"}
)


def pseudonymous_user_key(*, user):
    """결정적이면서 되돌릴 수 없는 사용자별 코호트 키를 반환한다.

    HMAC-SHA256(SECRET_KEY, str(user.pk))를 32자 16진수로 자른 값이다.
    별도 상수가 아니라 SECRET_KEY를 키로 써서 새 비밀값을 발급·회전할
    필요가 없다 — 대신 SECRET_KEY를 회전하면 코호트 연속성이 조용히
    끊기는데, 이 지표 용도에서는 원키 회전 내성이 필요 없으므로 감수한
    트레이드오프다.

    익명/미인증 사용자는 키로 쓸 pk가 없어 ""를 반환한다 — 호출자는
    ""를 "코호트 없음"으로 다뤄야지, 익명 히트들의 공유 코호트로
    취급하면 안 된다.

    보안 유의점: 이 가명화의 강도는 전적으로 SECRET_KEY가 비밀로
    유지되는 데 달려 있다. SECRET_KEY가 유출되면 user.pk는 작은 순차
    정수이므로 공격자가 있음직한 모든 i에 대해 HMAC(SECRET_KEY, str(i))를
    전수 계산해 user_key -> pk 역변환표를 즉시 만들 수 있다 — 키가
    노출되는 순간 가명화는 무효가 된다. 이 키를 인증·인가나 이 가명
    코호트 목적 외의 보안 용도로 재사용하지 마라.
    """
    if not getattr(user, "pk", None):
        return ""
    digest = hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        str(user.pk).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return digest[:32]


def record_event(*, event_name, user, target_type="", target_id=None, context=None):
    """AnalyticsEvent 한 행을 기록한다. 절대 예외를 던지지 않는다.

    금지된 컨텍스트 키(FORBIDDEN_CONTEXT_KEYS)는 저장 시도 전에 즉시
    ValueError로 실패한다 — 이건 호출자가 복구할 런타임 상황이 아니라
    개인정보를 실수로 남기지 않도록 막는 프로그래밍 오류 가드다.

    저장 자체는 최선 노력이다: 분석 기록이 그것이 붙어 있는 도메인 동작
    (예: 방문 기록 생성)을 절대 깨뜨리면 안 되므로, 저장 실패(예: DB
    장애)는 예외를 던지지 않고 잡아서 로깅만 한다. 삽입은 자체 중첩
    atomic()(세이브포인트) 안에서 실행되는데, 호출자가 이미 공유
    transaction.atomic() 안에 있을 수 있고(예:
    archive.services.complete_visit_with_record), PostgreSQL에서는 실패한
    문장이 롤백 전까지 감싸고 있는 트랜잭션 *전체*를 오염시키기 때문이다.
    세이브포인트가 없으면 예외를 잡아도 커넥션이 못 쓰게 남아 호출자의
    다음 도메인 쓰기가 TransactionManagementError로 실패한다. 세이브포인트가
    피해 범위를 이 삽입 하나로 한정한다.
    """
    context = context or {}
    forbidden = FORBIDDEN_CONTEXT_KEYS & context.keys()
    if forbidden:
        raise ValueError(
            f"context contains forbidden key(s): {', '.join(sorted(forbidden))}"
        )

    try:
        with transaction.atomic():
            AnalyticsEvent.objects.create(
                event_name=event_name,
                user_key=pseudonymous_user_key(user=user),
                target_type=target_type,
                target_id=target_id,
                context=context,
            )
    except Exception:
        logger.exception("Failed to record analytics event %r", event_name)


def distinct_user_key_count_since(*, days=7, offset=0):
    """지난 구간에서 기록된, 비어 있지 않은(식별된) user_key의 고유 개수.

    구간은 [now-(offset+days), now-offset) 반열림 구간이다
    (staff.queries.staff_actions_count_since와 같은 규약) — 경계에 걸친
    행이 두 번 세이지 않는다. offset을 늘리면 더 과거 구간과 비교할 수
    있다. ""(익명, pseudonymous_user_key 참고)는 하나의 공유 코호트가
    아니므로 제외한다."""
    window_end = timezone.now() - timedelta(days=offset)
    window_start = window_end - timedelta(days=days)
    return (
        AnalyticsEvent.objects.filter(created_at__gte=window_start, created_at__lt=window_end)
        .exclude(user_key="")
        .values("user_key")
        .distinct()
        .count()
    )


def event_name_counts_since(*, days=7, offset=0):
    """지난 구간에서 기록된 이벤트를 {event_name: count}로 반환한다.

    구간 규약은 distinct_user_key_count_since와 같다. 창 안에 행이 0개인
    event_name은 반환 dict에 아예 없다."""
    window_end = timezone.now() - timedelta(days=offset)
    window_start = window_end - timedelta(days=days)
    rows = (
        AnalyticsEvent.objects.filter(created_at__gte=window_start, created_at__lt=window_end)
        .values("event_name")
        .annotate(count=Count("id"))
    )
    return {row["event_name"]: row["count"] for row in rows}
