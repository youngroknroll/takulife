"""트랙 43-1 UI 다국어 기반 — 스태프 콘솔 뷰는 활성 언어와 무관하게
한국어로 강제 실행되고, 실행 후에는 원래 활성 언어로 복원된다."""
import re
import types

import pytest
from django.http import HttpResponse
from django.test import RequestFactory
from django.utils import translation

from staff.permissions import staff_console_required

pytestmark = pytest.mark.unit


# I18N-8
def test_스태프_콘솔_뷰는_활성_언어가_달라도_한국어로_실행되고_복원된다():
    translation.activate("en")
    try:
        captured = []

        def view_func(request):
            captured.append(translation.get_language())
            return HttpResponse("ok")

        request = RequestFactory().get("/")
        request.user = types.SimpleNamespace(is_authenticated=True, is_staff=True)

        staff_console_required(view_func)(request)

        assert captured[0] == "ko"
        assert translation.get_language() == "en"
    finally:
        translation.deactivate()


# I18N-20
def test_스태프_콘솔_뷰가_예외를_던져도_활성_언어는_복원된다():
    """`with translation.override("ko"):` 블록 안에서 뷰가 예외를 던져도
    컨텍스트 매니저의 __exit__이 실행돼 바깥 활성 언어가 되돌아온다."""
    translation.activate("en")
    try:

        def view_func(request):
            raise RuntimeError("simulated view failure")

        request = RequestFactory().get("/")
        request.user = types.SimpleNamespace(is_authenticated=True, is_staff=True)

        with pytest.raises(RuntimeError):
            staff_console_required(view_func)(request)

        assert translation.get_language() == "en"
    finally:
        translation.deactivate()


# C-14
@pytest.mark.django_db
@pytest.mark.parametrize("language", ["en", "ja", "zh-hans"])
def test_스태프_이벤트_목록은_영어_요청에서도_카테고리를_한국어로_보여_준다(
    staff_client, make_event, language
):
    _, client = staff_client()
    make_event(title="스태프 목록 행사", category="popup_store")

    resp = client.get("/staff/events/", HTTP_ACCEPT_LANGUAGE=language)

    assert resp.status_code == 200
    cells = re.findall(
        r'<td class="events-category-cell">\s*(.*?)\s*</td>',
        resp.content.decode(),
        flags=re.DOTALL,
    )
    assert cells == ["팝업스토어"]
