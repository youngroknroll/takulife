"""staff/views/ 하위 모듈이 공유하는 헬퍼.

값을 준비하는 로직만 여기 둔다. `StaffActionLog.objects.create()` 호출
자체는 각 호출부의 `transaction.atomic()` 블록 안에 남겨야 한다 — 로그
기록이 실패하면 그 행동 자체도 롤백돼야 하기 때문이다.
"""
import datetime

from django.conf import settings
from django.utils import timezone

from core.ip import get_client_ip


def _staff_action_metadata(request):
    return {
        "actor": request.user,
        "ip_address": get_client_ip(request),
        "user_agent": request.META.get("HTTP_USER_AGENT", ""),
    }


def _action_log_kwargs(
    metadata, action, *, target_draft=None, target_event=None, target_user=None, target_category=None
):
    """`request`가 아닌 이미 추출된 `metadata` 딕셔너리를 받는다.

    반복문 안에서 항목마다 호출되는 StaffDraftBulkApproveView._approve_one
    처럼 request 없이 metadata만 갖고 있는 호출부가 재추출 없이 재사용할
    수 있게 하기 위해서다. target_draft/target_event/target_user/target_category는
    넷 중 하나만 채워지고 나머지는 None으로 남는다.
    """
    return {
        "action": action,
        "target_draft": target_draft,
        "target_event": target_event,
        "target_user": target_user,
        "target_category": target_category,
        **metadata,
    }


def _validate_bulk_ids(ids, *, field_name, max_items):
    """일괄 처리 엔드포인트가 공유하는 구조 검사. 각 id가 실제로 존재하고
    처리 가능한 상태인지는 호출부의 반복문에서 항목별로 판단한다."""
    if not isinstance(ids, list) or not ids:
        return f"{field_name} must be a non-empty list."
    # 개수 상한 검사를 먼저 해서, 과도하게 큰 payload는 전체를 훑기 전에 걸러낸다.
    if len(ids) > max_items:
        return f"{field_name} must contain at most {max_items} ids."
    if not all(
        isinstance(item, int) and not isinstance(item, bool) for item in ids
    ):
        return f"{field_name} must contain only integers."
    return None


def _build_source_rows(sources):
    """소스별 신선도 상태를 계산해 붙인다. 대시보드와 수집 소스 화면(N1)이
    함께 쓴다.

    is_stale는 활성화된 소스에만 적용한다 — 비활성 소스는 원래 수집을
    안 하므로 오래된 last_checked_at이 문제가 아니다. 여러 조건이 동시에
    참일 때 우선순위는 disabled > error > stale > ok다 — 비활성 소스가
    오류로 잘못 표시되지 않게 하고, 실제로 실패 중인 소스를 단순 정체보다
    먼저 알리기 위해서다.
    """
    cutoff = timezone.now() - datetime.timedelta(hours=settings.DRAFT_SOURCE_STALE_HOURS)
    rows = []
    for source in sources:
        has_error = bool(source.last_error)
        is_stale = source.enabled and (
            source.last_checked_at is None or source.last_checked_at < cutoff
        )
        if not source.enabled:
            status_level = "disabled"
        elif has_error:
            status_level = "error"
        elif is_stale:
            status_level = "stale"
        else:
            status_level = "ok"
        rows.append(
            {
                "source": source,
                "has_error": has_error,
                "is_stale": is_stale,
                "status_level": status_level,
            }
        )
    return rows
