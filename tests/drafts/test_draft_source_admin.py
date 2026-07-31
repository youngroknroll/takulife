"""drafts DraftSource의 admin 등록 테스트. 모델이 존재하고 admin 목록에서
접근 가능한지만 확인하며, list_display 등 커스텀 admin 동작은 검증하지 않는다."""
import pytest

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_슈퍼유저는_드래프트_소스_관리자_목록_페이지에_접근할_수_있다(client, django_user_model):
    superuser = django_user_model.objects.create_superuser(
        email="admin@example.com", password="Aa1!strongpassword"
    )
    client.force_login(superuser)

    response = client.get("/admin/drafts/draftsource/")

    assert response.status_code == 200
