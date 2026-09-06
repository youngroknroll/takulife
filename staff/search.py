"""커맨드바 검색(`?q=`)의 경계 처리.

세 화면(드래프트 큐·이벤트 목록·감사 로그)이 같은 파라미터를 쓰므로 읽는
규칙을 여기 한 곳에 둔다.
"""

# 사람이 손으로 치는 검색어라 이 길이를 넘길 이유가 없다. 상한이 없으면
# 긴 문자열로 icontains 스캔을 반복시켜 DB를 물고 늘어질 수 있다.
MAX_SEARCH_LENGTH = 100

# 검색 폼이 다시 제출할 때 이어받으면 안 되는 키. q는 폼이 직접 넣고,
# page는 결과 집합이 바뀌므로 1쪽부터 다시 봐야 한다.
_EXCLUDED_FROM_FORM = ("q", "page")

SEARCHABLE_URL_NAMES = ("draft-list", "event-list", "audit-log", "account-list")


def search_term(request):
    """`?q=`를 정규화해 돌려준다. 상한을 넘으면 잘라 쓴다."""
    raw = request.GET.get("q", "")
    return raw.strip()[:MAX_SEARCH_LENGTH]


def search_form_hidden_params(request):
    """검색 폼이 그대로 다시 보내야 할 (키, 값) 목록.

    폼이 `q` 하나만 보내면 보고 있던 상태 필터·경고 드릴다운이 조용히
    풀린다 — `/staff/drafts/?status=pending`에서 검색하면 `status`가 사라진다.
    """
    pairs = []
    for key in request.GET:
        if key in _EXCLUDED_FROM_FORM:
            continue
        for value in request.GET.getlist(key):
            if value:
                pairs.append({"key": key, "value": value})
    return pairs
