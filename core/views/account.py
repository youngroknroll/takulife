"""계정 허브 뷰. 아카이브·컬렉션 집계를 모아 개인 요약을 보여준다."""
import logging

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

from accounts import services as accounts_services
from archive.queries import (
    user_collection_item_summary_counts,
    user_interest_count,
    user_personal_entry_counts,
    user_status_counts,
    user_visit_record_counts,
    user_visit_record_photo_count,
)

logger = logging.getLogger(__name__)


def _build_delete_targets(user):
    """탈퇴 화면의 "삭제될 항목" 6종 카운트. GET과 POST 두 실패 경로(비밀번호
    오류/락아웃) 모두 이 표를 보여줘야 한다 — 사용자가 탈퇴 여부를 판단하는
    근거라, 오류 한 번에 조용히 사라지면 안 된다(브라우저 실측 H1)."""
    return [
        {"label": "찜한 행사", "count": user_interest_count(user), "unit": "건"},
        {
            "label": "나의 일정",
            "count": sum(user_status_counts(user).values()),
            "unit": "건",
        },
        {
            "label": "다녀온 기록",
            "count": user_visit_record_counts(user)["total_count"],
            "unit": "건",
        },
        {
            "label": "기록 사진",
            "count": user_visit_record_photo_count(user),
            "unit": "장",
        },
        {
            "label": "컬렉션 굿즈",
            "count": user_collection_item_summary_counts(user)["total_count"],
            "unit": "건",
        },
        {
            "label": "직접 등록 항목",
            "count": user_personal_entry_counts(user)["total_count"],
            "unit": "건",
        },
    ]


@login_required
def mypage(request):
    user = request.user
    saved_count = sum(user_status_counts(user).values())
    visit_count = user_visit_record_counts(user)["total_count"]
    personal_entry_count = user_personal_entry_counts(user)["total_count"]
    interest_count = user_interest_count(user)
    collection_count = user_collection_item_summary_counts(user)["total_count"]

    # index_rows drives mypage.html's index list; row order and ink values
    # are fixed by the mypage brief (§1). Each row is rendered as a single
    # <a> spanning the whole row, so its accessible name concatenates
    # title + badge + description + count. Whenever the title already
    # contains the badge label, keep domain_label empty below so the
    # template's "{% if row.domain_label %}" skips a badge that would
    # otherwise repeat the title for screen readers (BIR M3; exact-match
    # "내 활동"/"내 활동" is just the special case of this rule).
    index_rows = [
        {
            "title": "내 컬렉션",
            "domain_label": "컬렉션",
            "ink": "brand",
            "description": "모은 굿즈를 한눈에 확인해요",
            "count": collection_count,
            "unit": "점",
            "url": "/collection/",
        },
        {
            "title": "내 활동",
            "domain_label": "내 활동",
            "ink": "teal",
            "description": "저장한 행사를 모아봐요",
            "count": saved_count,
            "unit": "건",
            "url": "/archive/",
        },
        {
            "title": "다녀온 기록",
            "domain_label": "내 활동",
            "ink": "teal",
            "description": "다녀온 행사를 기록해요",
            "count": visit_count,
            "unit": "건",
            "url": "/archive/visits/",
        },
        {
            "title": "직접 등록",
            "domain_label": "내 활동",
            "ink": "teal",
            "description": "비공식 장소·행사를 등록해요",
            "count": personal_entry_count,
            "unit": "곳",
            "url": "/archive/personal/",
        },
        {
            "title": "찜 목록",
            "domain_label": "내 활동",
            "ink": "pink",
            "description": "관심 있는 행사를 찜해요",
            "count": interest_count,
            "unit": "건",
            "url": "/archive/interests/",
        },
    ]
    for row in index_rows:
        if row["domain_label"] and row["domain_label"] in row["title"]:
            row["domain_label"] = ""

    password_changed_at = user.password_changed_at
    password_changed_display = accounts_services.format_password_changed_display(
        password_changed_at
    )

    return render(
        request,
        "core/mypage.html",
        {
            "saved_count": saved_count,
            "visit_count": visit_count,
            "personal_entry_count": personal_entry_count,
            "interest_count": interest_count,
            "collection_count": collection_count,
            "joined_year": user.date_joined.year,
            "password_changed_at": password_changed_at,
            "password_changed_display": password_changed_display,
            "index_rows": index_rows,
        },
    )


@login_required
def delete_account(request):
    """Password-reconfirmed account deletion request (10-day grace period).

    Moved here from accounts.views by the account-settings-editorial plan
    B5: GET must read archive counts for the 삭제 대상 요약, and accounts is
    not allowed to import archive (see
    tests/core/test_architecture_boundaries.py) — core/views/ is the one
    domain-composition seam the boundary guard allows. The password-lockout
    security rule itself stays owned by accounts.services
    (is_delete_locked / register_failed_delete_attempt).

    GET renders the confirmation form plus delete_targets (6 counts). POST
    verifies the current password then records the deletion request via
    accounts.services.request_deletion (see
    .docs/plans/2026-07-20-deletion-grace-period-plan.md) — the account
    itself is not deleted here; it survives for a 10-day grace period, purged
    later by accounts.management.commands.purge_deleted_accounts unless the
    user logs back in and cancels it. The session is flushed right after the
    request is recorded so the browser's existing cookie stops authenticating
    for the rest of this visit; the 완료 안내 payload is written to the
    session *after* logout() (logout() flushes the session, so writing
    before it would be lost).

    Staff accounts are blocked from self-deletion on both GET and POST
    (403) — the header no longer links here for a staff user (account_menu
    dropdown / settings page), but the UI hiding it is not itself a
    guarantee, so the view enforces it directly. Staff removal is a Django
    admin action only (superuser judgment call).
    """
    if request.user.is_staff:
        raise PermissionDenied

    if request.method == "POST":
        if accounts_services.is_delete_locked(request.user):
            return render(
                request,
                "account/delete_account.html",
                {
                    "field_errors": {"password": accounts_services.DELETE_LOCKOUT_MESSAGE},
                    "delete_targets": _build_delete_targets(request.user),
                },
            )

        password = request.POST.get("password", "")
        if not request.user.check_password(password):
            accounts_services.register_failed_delete_attempt(request.user)
            return render(
                request,
                "account/delete_account.html",
                {
                    "field_errors": {"password": "비밀번호가 올바르지 않습니다."},
                    "delete_targets": _build_delete_targets(request.user),
                },
            )

        accounts_services.reset_delete_attempts(request.user)
        user = request.user
        logger.info("Requesting account deletion user_pk=%s", user.pk)
        accounts_services.request_deletion(user)
        requested_at = user.deletion_requested_at
        scheduled_for = requested_at + accounts_services.DELETION_GRACE_PERIOD
        logout(request)
        # 세션 JSON 직렬화는 datetime을 그대로 왕복시키지 못하므로 ISO
        # 문자열로 적재한다 — accounts.views.delete_account_done이 파싱한다.
        request.session[accounts_services.DELETE_DONE_SESSION_KEY] = {
            "requested_at": requested_at.isoformat(),
            "scheduled_for": scheduled_for.isoformat(),
        }
        return redirect("account-delete-done-page")

    return render(
        request,
        "account/delete_account.html",
        {"field_errors": {}, "delete_targets": _build_delete_targets(request.user)},
    )
