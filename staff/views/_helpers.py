"""staff/views/ 하위 모듈이 공유하는 헬퍼.

값을 준비하는 로직만 여기 둔다. `StaffActionLog.objects.create()` 호출
자체는 각 호출부의 `transaction.atomic()` 블록 안에 남겨야 한다 — 로그
기록이 실패하면 그 행동 자체도 롤백돼야 하기 때문이다.
"""
from core.ip import get_client_ip


def _staff_action_metadata(request):
    return {
        "actor": request.user,
        "ip_address": get_client_ip(request),
        "user_agent": request.META.get("HTTP_USER_AGENT", ""),
    }


def _action_log_kwargs(metadata, action, *, target_draft=None, target_event=None):
    """`request`가 아닌 이미 추출된 `metadata` 딕셔너리를 받는다.

    반복문 안에서 항목마다 호출되는 StaffDraftBulkApproveView._approve_one
    처럼 request 없이 metadata만 갖고 있는 호출부가 재추출 없이 재사용할
    수 있게 하기 위해서다. target_draft/target_event는 둘 중 하나만
    채워지고 나머지는 None으로 남는다.
    """
    return {
        "action": action,
        "target_draft": target_draft,
        "target_event": target_event,
        **metadata,
    }
