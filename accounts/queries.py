"""스태프 계정 콘솔용 읽기 전용 계층.

계정 도메인이 자기 조회 로직을 소유한다(events/queries.py처럼 도메인이
자기 조회를 소유하는 구조). HTTP 관문·페이지네이션은 staff 뷰가 감싼다.
"""
from .models import User


def list_accounts_for_staff(search=""):
    """계정 콘솔 목록에 필요한 필드만 최신 가입순으로 반환한다."""
    qs = User.objects.all()
    term = search.strip()
    if term:
        qs = qs.filter(email__icontains=term)
    return qs.order_by("-date_joined").values(
        "id",
        "email",
        "date_joined",
        "last_login",
        "is_staff",
        "is_superuser",
        "is_active",
        "deletion_requested_at",
    )
