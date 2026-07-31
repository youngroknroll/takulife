"""`/staff/*` 전용 템플릿 컨텍스트 프로세서(B4).

모든 요청에 등록돼 있지만(config/settings.py TEMPLATES), staff 네임스페이스가
아닌 요청에서는 즉시 빈 dict를 반환해 소비자 페이지 요청마다 쿼리가 늘어나지
않게 한다.
"""
from drafts.queries import draft_review_stats


def sidebar_badge_counts(request):
    """사이드바 배지에 쓸 대기 드래프트 건수를 담는다.

    request.resolver_match가 None일 수 있다(미들웨어 순서, 404 등) — 이
    저장소는 그런 경우 request=None으로 넘어와 크래시한 전례가 있어
    getattr로 안전하게 처리한다.
    """
    resolver_match = getattr(request, "resolver_match", None)
    if resolver_match is None or resolver_match.app_name != "staff":
        return {}
    return {"sidebar_pending_draft_count": draft_review_stats()["pending"]}
