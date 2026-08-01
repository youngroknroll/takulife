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

    # index_rows가 mypage.html의 목록을 그린다. 각 행은 전체가 하나의
    # <a>로 렌더링돼 접근성 이름이 제목+배지+설명+개수를 이어붙인 값이
    # 된다. 제목에 이미 배지 라벨이 들어 있으면 아래에서 domain_label을
    # 비워, 템플릿의 "{% if row.domain_label %}"가 스크린리더에 제목을
    # 중복해서 읽어주는 배지를 건너뛰게 한다("내 활동"/"내 활동"처럼
    # 완전히 같은 경우도 이 규칙의 한 사례다).
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
    """비밀번호 재확인이 있는 계정 탈퇴 신청(10일 유예 기간).

    accounts.views에서 이곳으로 옮겨왔다: GET이 삭제 대상 요약을 위해
    archive 카운트를 읽어야 하는데 accounts는 archive를 임포트할 수 없어서
    (tests/core/test_architecture_boundaries.py 참고) — web/views/가 프레젠테이션
    조립을 위해 도메인 앱을 임포트할 수 있는 계층이다. 비밀번호 잠금 보안
    규칙 자체는 여전히 accounts.services가 소유한다
    (is_delete_locked / register_failed_delete_attempt).

    GET은 확인 폼과 delete_targets(6개 카운트)를 렌더링한다. POST는 현재
    비밀번호를 확인한 뒤 accounts.services.request_deletion으로 탈퇴
    신청을 기록한다 — 계정 자체는 여기서 삭제되지 않고 10일 유예
    기간 동안 살아 있다가, 사용자가 다시 로그인해 취소하지 않으면
    accounts.management.commands.purge_deleted_accounts가 나중에 지운다.
    신청 기록 직후 세션을 비워 브라우저의 기존 쿠키가 이번 방문 나머지
    동안 인증되지 않게 한다. 완료 안내 데이터는 logout() *이후*에
    세션에 쓴다(logout()이 세션을 비우므로 그 전에 쓰면 사라진다).

    스태프 계정은 GET/POST 모두 자율 탈퇴가 막혀 있다(403) — 스태프에게는
    헤더가 더 이상 이 경로로 링크하지 않지만, UI를 숨기는 것만으로는
    보장이 안 되므로 뷰가 직접 강제한다. 스태프 제거는 Django 관리자
    작업으로만 이뤄진다(슈퍼유저 판단).
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
