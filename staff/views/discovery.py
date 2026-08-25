"""스태프 콘솔 화면: 새 수집처 탐색 요청(POST /staff/source-discovery/request/).

로컬 러너 heartbeat가 신선할 때만 SourceDiscoveryRun을 pending으로 만든다.
러너 오프라인이거나 이미 활성 실행이 있으면 아무것도 만들지 않으므로
감사 로그도 남기지 않는다(staff_draft_discovery_run의 의도된 무동작 관행과
동일 — 실행이 실제로 만들어진 성공 경로만 감사 로그를 남긴다). 사용자당
60초 고정 창에 10회로 요청 빈도를 제한한다.
"""
import time

from django.contrib import messages
from django.core.cache import cache
from django.shortcuts import redirect

from drafts.discovery_runs import DiscoveryRunActiveError, RunnerOfflineError, create_run

from ..models import StaffActionLog
from ..permissions import staff_console_required
from ._helpers import _action_log_kwargs, _staff_action_metadata

# 60초 창당 허용 요청 수. cache.incr()는 쓰지 않는다 — DatabaseCache는
# incr()를 오버라이드하지 않아 BaseCache.incr()가 TTL 없는 set()으로
# 대체되고, 그러면 창이 요청마다 계속 연장된다(accounts/services.py의
# is_delete_locked/register_failed_delete_attempt와 동일한 결함이 재현됨).
# 대신 창 마감 시각을 레코드에 직접 저장해 비교한다.
DISCOVERY_THROTTLE_LIMIT = 10
DISCOVERY_THROTTLE_WINDOW_SECONDS = 60
DISCOVERY_THROTTLE_MESSAGE = "요청이 너무 잦습니다. 잠시 후 다시 시도하세요."


def _discovery_throttle_cache_key(user):
    return f"staff-source-discovery-throttle:{user.pk}"


def _discovery_request_throttled(user):
    key = _discovery_throttle_cache_key(user)
    now = time.time()
    record = cache.get(key)
    if not record or record["window_end"] <= now:
        record = {"count": 0, "window_end": now + DISCOVERY_THROTTLE_WINDOW_SECONDS}
    if record["count"] >= DISCOVERY_THROTTLE_LIMIT:
        return True
    record["count"] += 1
    cache.set(key, record, timeout=DISCOVERY_THROTTLE_WINDOW_SECONDS)
    return False


@staff_console_required
def staff_source_discovery_request(request):
    if request.method != "POST":
        return redirect("staff:dashboard")

    if _discovery_request_throttled(request.user):
        messages.info(request, DISCOVERY_THROTTLE_MESSAGE)
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
