"""Account deletion state machine (10-day grace period).

See .docs/plans/2026-07-20-deletion-grace-period-plan.md. No code path other
than accounts.management.commands.purge_deleted_accounts may call
`User.delete()` for a self-service deletion request — every other entry point
(the delete_account view, and later the login-cancels-deletion signal) only
reads or writes `deletion_requested_at` through the functions below.
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

# The grace period between a deletion request and eligibility for
# execute_pending_deletions' purge (see
# .docs/plans/2026-07-20-deletion-grace-period-plan.md).
DELETION_GRACE_PERIOD = timedelta(days=10)

# 탈퇴 완료 안내(accounts.views.delete_account_done) 전용 세션 키. 신청 시각·
# 삭제 예정일을 담는 쪽(core.views.account.delete_account)과 읽는 쪽
# (accounts.views) 둘 다 이 이름을 공유해야 하므로 양쪽이 이미 임포트하는
# accounts.services에 둔다. 메시지 프레임워크 대신 전용 키를 쓰는 이유는
# 키가 없으면(직접 URL 접근) 홈으로 보내 노출을 막기 위해서다.
DELETE_DONE_SESSION_KEY = "account_delete_done"

# Password re-check on the deletion view has no throttle of its own
# otherwise: axes only hooks the login backend, and allauth's
# ACCOUNT_RATE_LIMITS does not cover this custom view, so a hijacked session
# could brute-force the password indefinitely without this counter.
# Promoted here (from accounts/views.py) by the account-settings-editorial
# plan B5 — the deletion view itself moved to core/views/account.py (it needs
# to read archive counts, and accounts must not import archive), but the
# lockout security rule stays owned by accounts.
MAX_DELETE_PASSWORD_ATTEMPTS = 5
DELETE_PASSWORD_LOCKOUT_SECONDS = 60 * 15
DELETE_LOCKOUT_MESSAGE = "비밀번호를 여러 번 잘못 입력했습니다. 잠시 후 다시 시도해 주세요."


def delete_attempts_cache_key(user):
    return f"account-delete-attempts:{user.pk}"


def is_delete_locked(user):
    """True once `user` has exhausted the failure budget for this window.

    The window's deadline is stored explicitly in the cached record (rather
    than relied on implicitly via the cache entry's own physical TTL): the
    shared cache backend is DatabaseCache (config/settings.py CACHES, PR-0e),
    and unlike LocMemCache.incr(), DatabaseCache has no incr() override —
    BaseCache.incr() falls back to a plain `self.set(key, new_value)` call
    with no timeout argument, which resets the entry's physical TTL to the
    cache's default TIMEOUT on every failed attempt. If the fixed 15-minute
    window were represented only by that physical TTL, each new failure
    would silently shrink and refresh it, turning the intended fixed window
    into an effectively sliding, shorter one. Storing our own deadline and
    comparing it explicitly keeps the window fixed to the first failure
    regardless of what the cache backend does to the physical TTL.
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
    # The cache entry's own TTL only needs to outlive the stored deadline —
    # it is no longer the source of truth for the window (see
    # is_delete_locked above), so refreshing it on every write is safe.
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
    """Record `user` as pending deletion; the account itself is untouched.

    Every session belonging to `user` is invalidated here, not just the one
    that submitted the request — a panic deletion has to end an attacker's
    (or simply another device's) session too, or that session would keep
    working for the whole 10-day grace period (Security review, see
    .docs/plans/2026-07-20-deletion-grace-period-plan.md).
    """
    user.deletion_requested_at = timezone.now()
    user.save(update_fields=["deletion_requested_at"])
    for session in Session.objects.all():
        if session.get_decoded().get("_auth_user_id") == str(user.pk):
            session.delete()


def cancel_deletion(user):
    """Clear a pending deletion request; return the number of rows updated.

    The conditional `deletion_requested_at__isnull=False` update (rather than
    an unconditional save) makes the rowcount a reliable signal of whether a
    request actually existed and was cleared here — the caller (the
    login-cancels-deletion signal, and later the purge command's concurrency
    guard) can tell a real cancellation apart from a no-op without a second
    query.
    """
    return User.objects.filter(pk=user.pk, deletion_requested_at__isnull=False).update(
        deletion_requested_at=None
    )


def record_password_change(user):
    """Stamp `user.password_changed_at` with now; the sole write path for
    that field. Called from accounts.signals' allauth password-lifecycle
    receivers (password_changed, password_set, password_reset) — never
    written directly from a signal handler (see .docs mypage brief).
    """
    user.password_changed_at = timezone.now()
    user.save(update_fields=["password_changed_at"])


def execute_pending_deletions(now=None):
    """Purge every account whose grace period has fully elapsed.

    Each candidate is re-verified and deleted in its own transaction (never
    the whole batch in one transaction) so one row's outcome cannot block or
    roll back any other row. `select_for_update` re-reads under a lock
    immediately before deleting, so a `cancel_deletion` landing in the gap
    between the initial candidate scan and this transaction is respected
    (DEL-08) instead of being purged anyway. `user.delete()` here is the only
    place a self-service deletion request may hard-delete a row (plan
    invariant — every other path only reads/writes `deletion_requested_at`).

    A single row's failure (e.g. a CASCADE/signal error on one account) is
    isolated to that row and logged, not left to abort the whole sweep —
    this mirrors discover_drafts.py's per-item isolation. Returns a summary
    dict with `deleted` (pks actually removed) and `failed` (`(pk, str(exc))`
    pairs) so the caller (purge_deleted_accounts) can report and, if
    non-empty, raise.
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
            # except-ok: isolated per-row so one failure cannot block the rest
            logger.exception("Failed to purge pending-deletion user pk=%s", pk)
            failed.append((pk, str(exc)))
    return {"deleted": deleted_pks, "failed": failed}
