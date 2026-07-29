"""계정 허브 뷰. 아카이브·컬렉션 집계를 모아 개인 요약을 보여준다."""
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from archive.queries import (
    user_collection_item_summary_counts,
    user_interest_count,
    user_personal_entry_counts,
    user_status_counts,
    user_visit_record_counts,
)


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
    password_changed_display = (
        timezone.localtime(password_changed_at).strftime("%Y.%m.%d")
        if password_changed_at is not None
        else "변경 이력 없음"
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
