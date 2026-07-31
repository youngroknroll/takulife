"""스태프 콘솔 화면: 감사 로그 페이지네이션·필터(B8, N2, `/staff/audit-log/`).

D9(⚠️): StaffActionLog 전체 조회는 슈퍼유저 전용(staff/admin.py)이고,
운영자(is_staff)가 보는 이 화면은 행위자/행동/대상/시각만 담은 요약이어야
한다. list_staff_action_log(staff/queries.py)가 ip_address/user_agent를
애초에 select하지 않으므로 이 뷰는 그 필드를 구조적으로 볼 수 없다.
"""
from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.shortcuts import render

from ..action_labels import ACTION_LABELS
from ..models import StaffActionLog
from ..permissions import staff_console_required
from ..queries import STAFF_ACTION_LOG_PAGE_SIZE, list_staff_action_log


def _build_audit_log_rows(rows):
    """list_staff_action_log()의 요약 dict 행에 표시용 라벨을 붙인다."""
    built = []
    for row in rows:
        if row["target_draft_id"] is not None:
            target_label = row["target_draft__source_url"] or f"드래프트 #{row['target_draft_id']}"
        elif row["target_event_id"] is not None:
            target_label = row["target_event__title"] or f"이벤트 #{row['target_event_id']}"
        else:
            target_label = "-"
        built.append(
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "action": row["action"],
                "action_label": ACTION_LABELS.get(row["action"], row["action"]),
                "actor_email": row["actor__email"] or "(탈퇴한 사용자)",
                "target_label": target_label,
            }
        )
    return built


@staff_console_required
def staff_audit_log(request):
    selected_action = request.GET.get("action", "")
    if selected_action not in StaffActionLog.Action.values:
        selected_action = ""

    rows = list_staff_action_log(action=selected_action)
    paginator = Paginator(rows, STAFF_ACTION_LOG_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))
    log_rows = _build_audit_log_rows(page_obj.object_list)

    pager_query = "&" + urlencode([("action", selected_action)]) if selected_action else ""
    action_chips = [
        {"key": key, "label": ACTION_LABELS.get(key, key)} for key in StaffActionLog.Action.values
    ]

    return render(
        request,
        "staff/audit_log/list.html",
        {
            "log_rows": log_rows,
            "page_obj": page_obj,
            "selected_action": selected_action,
            "pager_query": pager_query,
            "action_chips": action_chips,
        },
    )
