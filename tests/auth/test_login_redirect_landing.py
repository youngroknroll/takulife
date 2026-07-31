"""목표 IA 계획 D4(.docs/plans/2026-07-16-target-ia-plan.md §3): 명시적인
``?next=`` 없는 로그인은 /archive/가 아니라 /collection/(컬렉션 우선
제품 진입점)로 도착해야 한다.
"""
import pytest

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_next_파라미터_없이_로그인하면_컬렉션_페이지로_리다이렉트된다(client, make_verified_user, valid_password):
    user = make_verified_user()

    response = client.post("/accounts/login/", {"login": user.email, "password": valid_password})

    assert response.status_code == 302
    assert response.url == "/collection/"
