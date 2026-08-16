"""drf-spectacular 전처리 훅 — 스태프 콘솔 전용 DRF 뷰가 공개 API 문서로 새는 것을 막는다."""


def preprocess_exclude_non_api_paths(endpoints, **kwargs):
    """endpoints는 (path, path_regex, method, callback) 튜플 목록이다 —
    "/api/"로 시작하지 않는 경로(예: /staff/ 콘솔 DRF 뷰)를 걸러낸다."""
    return [
        (path, path_regex, method, callback)
        for path, path_regex, method, callback in endpoints
        if path.startswith("/api/")
    ]
