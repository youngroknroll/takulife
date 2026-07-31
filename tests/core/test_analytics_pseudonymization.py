"""core.analytics.pseudonymous_user_key 검증
(.docs/plans/2026-07-14-stage0-deployment-foundation-plan.md §8).
"""
import pytest

from core.analytics import pseudonymous_user_key

pytestmark = pytest.mark.contract


@pytest.mark.django_db
def test_동일_사용자에게_의사식별자_키는_항상_같은_값을_반환한다(make_user):
    user = make_user()

    assert pseudonymous_user_key(user=user) == pseudonymous_user_key(user=user)


def test_의사식별자_키에는_원본_pk_값이_포함되지_않는다():
    # 1이나 2 같은 작은 순차 DB pk와 달리 우연히 hex 다이제스트 부분
    # 문자열로 나타날 리 없는 뚜렷한 pk 값을 쓴다 — pseudonymous_user_key는
    # `.pk`만 읽으므로 가벼운 대역만으로 충분하고 DB 의존도 피할 수 있다.
    from types import SimpleNamespace

    user = SimpleNamespace(pk=918273645918273)

    key = pseudonymous_user_key(user=user)

    assert str(user.pk) not in key


@pytest.mark.django_db
def test_서로_다른_사용자의_의사식별자_키는_서로_다르다(make_user):
    first = make_user(email="first@example.com", username="first")
    second = make_user(email="second@example.com", username="second")

    assert pseudonymous_user_key(user=first) != pseudonymous_user_key(user=second)


def test_익명_사용자의_의사식별자_키는_빈_문자열이다():
    from django.contrib.auth.models import AnonymousUser

    assert pseudonymous_user_key(user=AnonymousUser()) == ""
