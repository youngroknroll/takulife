"""트랙 43-1 UI 다국어 — 스태프 DRF API(`staff/api_urls.py`)는
`staff_console_required`(Django 뷰 데코레이터)를 거치지 않으므로, 활성
언어가 한국어가 아니어도 DRF 내장 오류 문구가 요청 언어로 번역돼 나올
위험이 있다. 스태프 API는 항상 한국어 문구를 돌려줘야 한다. (존재하지
않는 pk의 404는 Django `get_object_or_404`의 영어 고정 문구라 언어 무관
검증에는 405 MethodNotAllowed를 쓴다.)"""

import inspect

import pytest
from django.urls import URLPattern, URLResolver, reverse
from rest_framework.views import APIView

import staff.api_urls as staff_api_urls
import staff.urls as staff_urls

pytestmark = pytest.mark.web


def _iter_api_view_routes(urlpatterns):
    """urlpatterns를 재귀로 훑어 DRF `APIView` 서브클래스로 뜬 라우트만
    `(url_name, view_cls, callback)`로 모은다 — 중첩 `include()`가 생겨도
    같은 방식으로 수집한다."""
    for entry in urlpatterns:
        if isinstance(entry, URLResolver):
            yield from _iter_api_view_routes(entry.url_patterns)
        elif isinstance(entry, URLPattern):
            view_cls = getattr(entry.callback, "cls", None)
            if inspect.isclass(view_cls) and issubclass(view_cls, APIView):
                yield entry.name, view_cls, entry.callback


def _missing_draft_detail_url():
    return reverse("event-draft-detail", kwargs={"pk": 999_999_999})


# I18N-18
@pytest.mark.django_db
def test_스태프_API_오류_문구는_요청_언어와_무관하게_한국어다(admin_client):
    """스태프 API의 DRF 번역 문구(허용되지 않는 메서드 405)는 요청 언어와
    무관하게 같아야 한다 — 404는 Django 영어 문구라 이 검증에 쓸 수 없다."""
    url = _missing_draft_detail_url()

    response_ja = admin_client.delete(url, HTTP_ACCEPT_LANGUAGE="ja")
    response_ko = admin_client.delete(url, HTTP_ACCEPT_LANGUAGE="ko")

    assert response_ja.status_code == 405
    assert response_ko.status_code == 405
    assert response_ja.json()["detail"] == response_ko.json()["detail"]


# I18N-25
def test_스태프_URL의_모든_DRF_뷰는_한국어_고정_관문으로_감싸져_있다():
    """스태프 화면이 호출하는 JSON 엔드포인트는 전부 `staff_api_korean`을
    거쳐야 한다 — 새 스태프 API가 같은 방식으로 빠지는 것을 막는 구조 가드다."""
    routes = list(_iter_api_view_routes(staff_urls.urlpatterns)) + list(
        _iter_api_view_routes(staff_api_urls.urlpatterns)
    )

    # staff/api_urls.py 3개(event-drafts·event-draft-stats·event-draft-detail)
    # + staff/urls.py 9개(draft-bulk-approve·draft-bulk-reject·draft-approve·
    # draft-reject·draft-reopen·event-bulk-unpublish·event-publish-status·
    # event-verified·discovery-live) = 12개 [실측 rg] — 숫자를 고정해 공허
    # 통과(대상 0건인데 위반도 0건)를 막는다.
    assert len(routes) == 12, [f"{cls.__name__} ({name})" for name, cls, _ in routes]

    violations = [
        f"{view_cls.__name__} ({name})"
        for name, view_cls, callback in routes
        if not getattr(callback, "staff_api_korean", False)
    ]

    assert violations == []
