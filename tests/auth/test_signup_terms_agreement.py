"""Signup requires explicit terms/privacy-policy agreement
(accounts.forms.SignupForm, ACCOUNT_FORMS)."""
from django.utils import timezone

import pytest

SIGNUP_URL = "/accounts/signup/"


@pytest.mark.django_db
def test_signup_without_terms_agreed_is_rejected(client, django_user_model, valid_password):
    response = client.post(
        SIGNUP_URL,
        {
            "email": "noagreement@example.com",
            "password1": valid_password,
            "password2": valid_password,
        },
    )

    # Re-rendered with a form error, not redirected to the "check your
    # email" page.
    assert response.status_code == 200
    assert not django_user_model.objects.filter(email="noagreement@example.com").exists()


@pytest.mark.django_db
def test_signup_with_terms_agreed_creates_user_and_records_timestamp(
    client, django_user_model, valid_password
):
    before = timezone.now()

    response = client.post(
        SIGNUP_URL,
        {
            "email": "agreed@example.com",
            "password1": valid_password,
            "password2": valid_password,
            "terms_agreed": "on",
        },
    )

    assert response.status_code == 302
    user = django_user_model.objects.get(email="agreed@example.com")
    assert user.terms_agreed_at is not None
    assert user.terms_agreed_at >= before


@pytest.mark.django_db
def test_signup_page_renders_terms_agreement_checkbox(client):
    response = client.get(SIGNUP_URL)

    assert response.status_code == 200
    body = response.content.decode("utf-8", "ignore")
    assert 'name="terms_agreed"' in body
