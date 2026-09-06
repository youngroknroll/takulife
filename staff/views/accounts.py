"""스태프 계정 운영 화면(`/staff/accounts/`) — 트랙 19 H1.

조작 주체는 슈퍼유저 한정(`superuser_console_required`)이고, 상태 변경은
목표 상태 지정(`enabled` "1"/"0")과 서버 렌더 2단계 확인
(`staff/views/events.py`의 삭제 확인 패턴과 같은 흐름)을 거친다.
"""
from urllib.parse import urlencode

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts import services as accounts_services
from accounts.models import User
from accounts.queries import list_accounts_for_staff

from ..models import StaffActionLog
from ..permissions import superuser_console_required
from ..search import search_term
from ._helpers import _action_log_kwargs, _staff_action_metadata

STAFF_ACCOUNT_LISTING_PAGE_SIZE = 20

# 뷰 본문 문자열이 아니라 여기서 명시 매핑해야 "true"·"2" 같은 truthy 값이
# 조용히 통과하지 않는다(SRR Medium — 목표 상태 오조작 차단).
_ENABLED_VALUES = {"1": True, "0": False}

_STAFF_LABELS = {
    True: ("검수 권한 부여", "이 계정에 검수 권한을 부여해 스태프 콘솔에 접근할 수 있게 합니다."),
    False: ("검수 권한 해제", "이 계정의 검수 권한을 해제해 스태프 콘솔 접근을 막습니다."),
}
_ACTIVE_LABELS = {
    True: ("계정 재활성화", "이 계정을 다시 활성화해 로그인할 수 있게 합니다."),
    False: ("계정 비활성화", "이 계정을 비활성화해 더 이상 로그인할 수 없게 합니다."),
}


def _account_status_key(row):
    if row["deletion_requested_at"] is not None:
        return "deletion_pending"
    return "active" if row["is_active"] else "inactive"


def _account_role_key(row):
    if row["is_superuser"]:
        return "superuser"
    if row["is_staff"]:
        return "staff"
    return "member"


@superuser_console_required
def staff_accounts(request):
    search = search_term(request)
    rows = list_accounts_for_staff(search=search)
    paginator = Paginator(rows, STAFF_ACCOUNT_LISTING_PAGE_SIZE)
    page_obj = paginator.get_page(request.GET.get("page"))
    account_rows = [
        {
            **row,
            "status_key": _account_status_key(row),
            "role_key": _account_role_key(row),
        }
        for row in page_obj.object_list
    ]
    pager_query = "&" + urlencode([("q", search)]) if search else ""

    return render(
        request,
        "staff/accounts/list.html",
        {
            "account_rows": account_rows,
            "page_obj": page_obj,
            "pager_query": pager_query,
            "search": search,
        },
    )


@superuser_console_required
def staff_account_detail(request, pk):
    account = get_object_or_404(User, pk=pk)
    deletion_scheduled_for = None
    if account.deletion_requested_at is not None:
        deletion_scheduled_for = account.deletion_requested_at + accounts_services.DELETION_GRACE_PERIOD

    return render(
        request,
        "staff/accounts/detail.html",
        {
            "account": account,
            "deletion_scheduled_for": deletion_scheduled_for,
            "is_protected": account.is_superuser,
        },
    )


def _apply_flag_change(request, pk, *, field, service, action_map, labels):
    enabled_raw = request.POST.get("enabled")
    if enabled_raw not in _ENABLED_VALUES:
        return HttpResponseBadRequest("enabled는 1 또는 0만 허용합니다.")
    enabled = _ENABLED_VALUES[enabled_raw]
    detail_url = reverse("staff:account-detail", args=[pk])
    action_label, description = labels[enabled]

    if request.POST.get("confirmed") != "yes":
        account = get_object_or_404(User, pk=pk)
        return render(
            request,
            "staff/accounts/confirm.html",
            {
                "account": account,
                "field": field,
                "enabled": enabled,
                "action_label": action_label,
                "description": description,
                "post_url": reverse(f"staff:account-set-{field}", args=[pk]),
            },
        )

    try:
        with transaction.atomic():
            # 목표 상태 지정이라도 읽고-바꾸는 흐름이라 잠그지 않으면 동시
            # 요청이 같은 상태를 읽고 경쟁한다(게시 토글과 같은 이유).
            target = get_object_or_404(User.objects.select_for_update(), pk=pk)
            changed = service(target, enabled=enabled)
            if changed:
                StaffActionLog.objects.create(
                    **_action_log_kwargs(
                        _staff_action_metadata(request),
                        action_map[enabled],
                        target_user=target,
                    )
                )
    except accounts_services.ProtectedAccountError:
        messages.error(request, "전체 권한(superuser) 계정은 여기서 변경할 수 없습니다.")
        return redirect(detail_url)

    if changed:
        messages.success(request, f"{action_label}이(가) 적용되었습니다.")
    else:
        messages.info(request, "이미 해당 상태라 변경하지 않았습니다.")
    return redirect(detail_url)


@superuser_console_required
@require_POST
def staff_account_set_staff(request, pk):
    return _apply_flag_change(
        request,
        pk,
        field="staff",
        service=accounts_services.set_staff_flag,
        action_map={
            True: StaffActionLog.Action.STAFF_GRANT,
            False: StaffActionLog.Action.STAFF_REVOKE,
        },
        labels=_STAFF_LABELS,
    )


@superuser_console_required
@require_POST
def staff_account_set_active(request, pk):
    return _apply_flag_change(
        request,
        pk,
        field="active",
        service=accounts_services.set_active_flag,
        action_map={
            True: StaffActionLog.Action.USER_REACTIVATE,
            False: StaffActionLog.Action.USER_DEACTIVATE,
        },
        labels=_ACTIVE_LABELS,
    )
