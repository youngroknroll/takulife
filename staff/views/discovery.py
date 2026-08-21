"""스태프 콘솔 화면: 새 수집처 탐색 요청(POST /staff/source-discovery/request/).

로컬 러너 heartbeat가 신선할 때만 SourceDiscoveryRun을 pending으로 만든다.
러너 오프라인이거나 이미 활성 실행이 있으면 아무것도 만들지 않으므로
감사 로그도 남기지 않는다(staff_draft_discovery_run의 의도된 무동작 관행과
동일 — 실행이 실제로 만들어진 성공 경로만 감사 로그를 남긴다).
"""
from django.contrib import messages
from django.shortcuts import redirect

from drafts.discovery_runs import DiscoveryRunActiveError, RunnerOfflineError, create_run

from ..models import StaffActionLog
from ..permissions import staff_console_required
from ._helpers import _action_log_kwargs, _staff_action_metadata


@staff_console_required
def staff_source_discovery_request(request):
    if request.method != "POST":
        return redirect("staff:dashboard")

    try:
        create_run(requested_by=request.user)
    except RunnerOfflineError:
        messages.info(
            request,
            "로컬 러너 오프라인 — 개인 맥의 러너가 실행 중인지 확인하세요.",
        )
        return redirect("staff:dashboard")
    except DiscoveryRunActiveError:
        messages.info(request, "이미 진행 중인 탐색 실행이 있습니다.")
        return redirect("staff:dashboard")

    StaffActionLog.objects.create(
        **_action_log_kwargs(_staff_action_metadata(request), StaffActionLog.Action.SOURCE_DISCOVER)
    )
    messages.success(request, "새 수집처 탐색 요청을 만들었습니다. 러너가 곧 가져갑니다.")

    return redirect("staff:dashboard")
