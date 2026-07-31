"""계정 탈퇴 상태 기계(10일 유예 기간).

accounts.management.commands.purge_deleted_accounts 외의 어떤 코드 경로도
자율 탈퇴 신청에 대해 `User.delete()`를 호출해서는 안 된다 — 그 외 모든
진입점(delete_account 뷰, 로그인 시 취소 신호)은 아래 함수들을 통해서만
`deletion_requested_at`을 읽거나 쓴다.
"""
import logging
import time
from datetime import timedelta

from django.contrib.sessions.models import Session
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from .models import User

logger = logging.getLogger(__name__)

# 탈퇴 신청과 execute_pending_deletions의 실제 삭제 대상이 되는 시점 사이의 유예 기간.
DELETION_GRACE_PERIOD = timedelta(days=10)

# 탈퇴 완료 안내(accounts.views.delete_account_done) 전용 세션 키. 신청 시각·
# 삭제 예정일을 담는 쪽(core.views.account.delete_account)과 읽는 쪽
# (accounts.views) 둘 다 이 이름을 공유해야 하므로 양쪽이 이미 임포트하는
# accounts.services에 둔다. 메시지 프레임워크 대신 전용 키를 쓰는 이유는
# 키가 없으면(직접 URL 접근) 홈으로 보내 노출을 막기 위해서다.
DELETE_DONE_SESSION_KEY = "account_delete_done"

# 탈퇴 화면의 비밀번호 재확인은 이게 없으면 속도 제한이 전혀 없다: axes는
# 로그인 백엔드에만 걸리고 allauth의 ACCOUNT_RATE_LIMITS도 이 커스텀 뷰를
# 커버하지 않으므로, 탈취된 세션이 이 카운터 없이는 무한히 비밀번호를
# 무차별 대입할 수 있다. 탈퇴 뷰 자체는 core/views/account.py로
# 옮겨졌지만(archive 카운트를 읽어야 하는데 accounts는 archive를 임포트할
# 수 없어서) 잠금 보안 규칙은 계속 accounts가 소유한다.
MAX_DELETE_PASSWORD_ATTEMPTS = 5
DELETE_PASSWORD_LOCKOUT_SECONDS = 60 * 15
DELETE_LOCKOUT_MESSAGE = "비밀번호를 여러 번 잘못 입력했습니다. 잠시 후 다시 시도해 주세요."


def delete_attempts_cache_key(user):
    return f"account-delete-attempts:{user.pk}"


def is_delete_locked(user):
    """`user`가 이 시간 창에서 실패 허용 횟수를 다 썼으면 True.

    창의 마감 시각을 캐시 항목의 물리적 TTL에 암묵적으로 맡기지 않고
    레코드 안에 직접 저장한다: 공유 캐시 백엔드가 DatabaseCache인데,
    LocMemCache.incr()와 달리 DatabaseCache는 incr()를 오버라이드하지
    않아서 BaseCache.incr()가 timeout 없는 `self.set(key, new_value)`로
    대체 실행되고, 이 때문에 실패할 때마다 항목의 물리적 TTL이 캐시 기본
    TIMEOUT으로 초기화된다. 고정 15분 창을 물리적 TTL만으로 표현하면 실패가
    거듭될수록 창이 조용히 줄어들고 갱신되어 의도한 고정 창이 사실상 더
    짧은 슬라이딩 창이 돼버린다. 마감 시각을 직접 저장하고 비교하면 캐시
    백엔드가 물리적 TTL을 어떻게 다루든 첫 실패 시점 기준으로 창이 고정된다.
    """
    record = cache.get(delete_attempts_cache_key(user))
    if not record or record["deadline"] <= time.time():
        return False
    return record["count"] >= MAX_DELETE_PASSWORD_ATTEMPTS


def register_failed_delete_attempt(user):
    key = delete_attempts_cache_key(user)
    now = time.time()
    record = cache.get(key)
    if not record or record["deadline"] <= now:
        record = {"count": 0, "deadline": now + DELETE_PASSWORD_LOCKOUT_SECONDS}
    record["count"] += 1
    if record["count"] == MAX_DELETE_PASSWORD_ATTEMPTS:
        logger.warning(
            "Account deletion password lockout triggered for user %s after %s failed attempts",
            user.pk,
            record["count"],
        )
    # 캐시 항목 자체의 TTL은 저장된 마감 시각보다만 오래 살아 있으면 된다 —
    # 창의 기준은 더 이상 이 TTL이 아니므로(위 is_delete_locked 참고)
    # 쓸 때마다 갱신해도 안전하다.
    cache.set(key, record, timeout=DELETE_PASSWORD_LOCKOUT_SECONDS)


def reset_delete_attempts(user):
    cache.delete(delete_attempts_cache_key(user))


def format_password_changed_display(password_changed_at):
    """password_changed_at(UTC aware datetime|None)을 화면 표시용 로컬
    타임존 날짜 문자열로 바꾼다. 마이페이지와 계정 설정 화면이 같은 사실을
    다르게 표기하지 않도록 공유하는 단일 소스."""
    if password_changed_at is None:
        return "변경 이력 없음"
    return timezone.localtime(password_changed_at).strftime("%Y.%m.%d")


def request_deletion(user):
    """`user`를 탈퇴 대기 상태로 기록한다. 계정 자체는 아직 그대로다.

    신청을 제출한 세션 하나뿐 아니라 `user`의 모든 세션을 여기서 무효화한다
    — 공격자(혹은 그냥 다른 기기)의 세션도 함께 끝내야, 그 세션이 10일
    유예 기간 내내 계속 살아 있는 일을 막을 수 있다(보안 검토 결과).
    """
    user.deletion_requested_at = timezone.now()
    user.save(update_fields=["deletion_requested_at"])
    for session in Session.objects.all():
        if session.get_decoded().get("_auth_user_id") == str(user.pk):
            session.delete()


def cancel_deletion(user):
    """대기 중인 탈퇴 신청을 지운다. 갱신된 행 수를 반환한다.

    무조건 save() 대신 `deletion_requested_at__isnull=False` 조건부 update를
    쓰는 이유는, 반환된 행 수만으로 실제 신청이 있었고 지금 지워졌는지를
    호출자(로그인 시 취소 신호, 삭제 명령의 동시성 가드)가 추가 쿼리 없이
    판단할 수 있게 하기 위해서다.
    """
    return User.objects.filter(pk=user.pk, deletion_requested_at__isnull=False).update(
        deletion_requested_at=None
    )


def record_password_change(user):
    """`user.password_changed_at`을 현재 시각으로 찍는다. 이 필드에 쓰는
    유일한 경로다. accounts.signals의 allauth 비밀번호 관련 수신자
    (password_changed, password_set, password_reset)에서 호출되며, 신호
    핸들러가 직접 쓰는 일은 없다.
    """
    user.password_changed_at = timezone.now()
    user.save(update_fields=["password_changed_at"])


def execute_pending_deletions(now=None):
    """유예 기간이 완전히 끝난 모든 계정을 삭제한다.

    각 후보는 각자의 트랜잭션에서 다시 검증하고 삭제한다(전체를 한
    트랜잭션으로 묶지 않는다) — 한 행의 결과가 다른 행을 막거나 되돌리지
    않게 하기 위해서다. `select_for_update`가 삭제 직전에 잠금 상태로 다시
    읽으므로, 최초 후보 조회와 이 트랜잭션 사이에 `cancel_deletion`이
    들어오면 그대로 존중되고 삭제되지 않는다. 여기 `user.delete()`가
    자율 탈퇴 신청이 실제로 행을 삭제하는 유일한 지점이다(그 외 경로는
    전부 `deletion_requested_at`만 읽거나 쓴다).

    한 행의 실패(예: 한 계정의 CASCADE/신호 오류)는 그 행에만 격리되어
    로깅되고 전체 처리를 중단시키지 않는다. `deleted`(실제로 지워진
    pk)와 `failed`(`(pk, str(exc))` 쌍)를 담은 요약 dict를 반환해
    호출자(purge_deleted_accounts)가 보고하고, 실패가 있으면 예외를
    던질 수 있게 한다.
    """
    now = now or timezone.now()
    cutoff = now - DELETION_GRACE_PERIOD
    candidate_pks = list(
        User.objects.filter(deletion_requested_at__lte=cutoff).values_list("pk", flat=True)
    )
    deleted_pks = []
    failed = []
    for pk in candidate_pks:
        try:
            with transaction.atomic():
                user = (
                    User.objects.select_for_update()
                    .filter(pk=pk, deletion_requested_at__lte=cutoff)
                    .first()
                )
                if user is not None:
                    user.delete()
                    deleted_pks.append(pk)
        except Exception as exc:
            # except-ok: 한 건이 실패해도 나머지 파기는 계속돼야 하므로 행마다 격리한다
            logger.exception("Failed to purge pending-deletion user pk=%s", pk)
            failed.append((pk, str(exc)))
    return {"deleted": deleted_pks, "failed": failed}
