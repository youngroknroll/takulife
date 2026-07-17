"""core.analytics.pseudonymous_user_key (PR-0e checkpoint B2).

(.docs/plans/2026-07-14-stage0-deployment-foundation-plan.md §8 PR-0e)
"""
import pytest

from core.analytics import pseudonymous_user_key

pytestmark = pytest.mark.contract


@pytest.mark.django_db
def test_동일_사용자에게_의사식별자_키는_항상_같은_값을_반환한다(make_user):
    user = make_user()

    assert pseudonymous_user_key(user) == pseudonymous_user_key(user)


def test_의사식별자_키에는_원본_pk_값이_포함되지_않는다():
    # A distinctive, non-coincidental pk value (unlike a small sequential DB
    # pk such as 1 or 2, which could trivially appear as a hex-digest
    # substring by chance) — pseudonymous_user_key only reads `.pk`, so a
    # lightweight stand-in is sufficient and avoids a DB dependency here.
    from types import SimpleNamespace

    user = SimpleNamespace(pk=918273645918273)

    key = pseudonymous_user_key(user)

    assert str(user.pk) not in key


@pytest.mark.django_db
def test_서로_다른_사용자의_의사식별자_키는_서로_다르다(make_user):
    first = make_user(email="first@example.com", username="first")
    second = make_user(email="second@example.com", username="second")

    assert pseudonymous_user_key(first) != pseudonymous_user_key(second)


def test_익명_사용자의_의사식별자_키는_빈_문자열이다():
    from django.contrib.auth.models import AnonymousUser

    assert pseudonymous_user_key(AnonymousUser()) == ""
