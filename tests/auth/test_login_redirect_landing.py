"""Target IA plan D4 (.docs/plans/2026-07-16-target-ia-plan.md §3): a login
with no explicit ``?next=`` must land on /collection/ (the collection-first
product entry point), not /archive/.
"""
import pytest


@pytest.mark.django_db
def test_login_without_next_redirects_to_collection(client, make_verified_user, valid_password):
    user = make_verified_user()

    response = client.post("/accounts/login/", {"login": user.email, "password": valid_password})

    assert response.status_code == 302
    assert response.url == "/collection/"
