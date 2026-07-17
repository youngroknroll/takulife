"""Tests for the drafts DraftSource admin registration (PR-2 of the
auto-discovery plan, prompt_plan.md §2-1). Registration-only: this proves the
model exists and is reachable through the admin changelist, not any custom
admin behavior (list_display, filters, etc. are not enforced here).
"""
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
