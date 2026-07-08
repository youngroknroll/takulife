"""Tests for the drafts DraftSource admin registration (PR-2 of the
auto-discovery plan, prompt_plan.md §2-1). Registration-only: this proves the
model exists and is reachable through the admin changelist, not any custom
admin behavior (list_display, filters, etc. are not enforced here).
"""
import pytest


@pytest.mark.django_db
def test_superuser_can_view_draft_source_admin_changelist(client, django_user_model):
    superuser = django_user_model.objects.create_superuser(
        email="admin@example.com", password="Aa1!strongpassword"
    )
    client.force_login(superuser)

    response = client.get("/admin/drafts/draftsource/")

    assert response.status_code == 200
