"""탈퇴 완료 안내 화면 (/accounts/delete/done/, account-settings-editorial
계획서 B6).

오케스트레이터 판정: 탈퇴 POST 성공은 (기존대로) 302이며, `logout()` 이후
전용 세션 키에 신청 시각·삭제 예정일을 적재한 뒤 이 경로로 리다이렉트한다.
완료 뷰는 그 세션 키를 pop하고, 키가 없으면(직접 URL 접근) 홈으로 보낸다.
"""
import pytest
from django.urls import reverse

DELETE_URL = "/accounts/delete/"
DELETE_DONE_URL = "/accounts/delete/done/"


@pytest.mark.django_db
@pytest.mark.web
def test_탈퇴에_성공하면_완료_안내_화면에_신청_시각과_삭제_예정일이_표시된다(
    client, make_user, valid_password
):
    user = make_user(password=valid_password)
    client.force_login(user)

    response = client.post(DELETE_URL, {"password": valid_password}, follow=True)

    assert reverse("account-delete-done-page") == DELETE_DONE_URL
    assert response.redirect_chain[-1][0] == DELETE_DONE_URL
    assert response.status_code == 200
    assert response.context["deletion_requested_at"] is not None
    assert response.context["deletion_scheduled_for"] is not None
    assert (
        response.context["deletion_scheduled_for"]
        > response.context["deletion_requested_at"]
    )


@pytest.mark.django_db
@pytest.mark.web
def test_세션에_탈퇴_정보가_없는_상태로_완료_안내_화면에_직접_접근하면_홈으로_리다이렉트된다(client):
    response = client.get(DELETE_DONE_URL)

    assert response.status_code == 302
    assert response["Location"] == "/"
