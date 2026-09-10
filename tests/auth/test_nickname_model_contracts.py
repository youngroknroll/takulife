"""닉네임 대소문자 무시 유일성은 DB UniqueConstraint(Lower)로도 강제된다
(폼을 거치지 않는 ORM 직접 경로 대비, 트랙 29 NICK-08)."""
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

import pytest

pytestmark = pytest.mark.domain


@pytest.mark.django_db
def test_대소문자만_다른_닉네임은_DB_제약으로도_저장할_수_없다(django_user_model):
    django_user_model.objects.create_user(
        email="a@example.com", password=None, nickname="Taku"
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            django_user_model.objects.create_user(
                email="b@example.com", password=None, nickname="taku"
            )


@pytest.mark.django_db
def test_매니저로_예약어_닉네임을_만들면_거부된다(django_user_model):
    with pytest.raises(ValidationError):
        django_user_model.objects.create_user(
            email="c@example.com", password=None, nickname="admin"
        )


@pytest.mark.django_db
def test_매니저는_닉네임을_정규화해_저장한다(django_user_model):
    user = django_user_model.objects.create_user(
        email="d@example.com", password=None, nickname="  ａｂｃ "
    )

    assert user.nickname == "abc"


@pytest.mark.django_db
def test_닉네임_없이_매니저로_만들면_거부된다(django_user_model):
    with pytest.raises(ValueError):
        django_user_model.objects.create_user(email="e@example.com", password=None)
