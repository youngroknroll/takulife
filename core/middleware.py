"""쿼리 문자열이 붙은 요청을 특정 크롤러에게서만 거부하는 미들웨어."""

from django.http import HttpResponseForbidden

# 이 크롤러가 달력·목록의 쿼리 주소를 끝없이 따라가 대역폭이 초과됐다.
# robots.txt를 다시 읽기 전에도 막으려고 서버에서 직접 거부한다.
BLOCKED_QUERY_CRAWLER_TOKENS = ("claudebot",)


def _is_blocked_crawler_query(request):
    if not request.META.get("QUERY_STRING"):
        return False
    user_agent = request.META.get("HTTP_USER_AGENT", "").lower()
    return any(token in user_agent for token in BLOCKED_QUERY_CRAWLER_TOKENS)


class CrawlerQueryBlockMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if _is_blocked_crawler_query(request):
            return HttpResponseForbidden("", content_type="text/plain")
        return self.get_response(request)
