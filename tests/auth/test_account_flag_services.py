"""accounts.services 계정 플래그 변경(스태프 부여/회수·활성화/비활성화) —
트랙 19 H1: 스태프 콘솔 관문 없이 서비스 계약만 검증한다(T4·T5).

목표 상태 지정(토글 아님)이라 enabled=True/False가 대상의 최종 상태를
그대로 뜻한다. 슈퍼유저 대상은 조작 주체가 슈퍼유저 한정이라 자기 자신도
보호 대상이 되므로 ProtectedAccountError로 막는다(승인 범위 2번).
"""
import pytest

from accounts import services

pytestmark = pytest.mark.domain


@pytest.mark.django_db
def test_스태프가_아닌_대상에_enabled_True로_set_staff_flag를_호출하면_스태프가_되고_True를_반환한다(make_user):
    user = make_user(is_staff=False)

    changed = services.set_staff_flag(user, enabled=True)

    assert changed is True
    user.refresh_from_db()
    assert user.is_staff is True


@pytest.mark.django_db
def test_이미_스태프인_대상에_enabled_True로_set_staff_flag를_호출하면_무변경으로_False를_반환한다(make_user):
    user = make_user(is_staff=True)

    changed = services.set_staff_flag(user, enabled=True)

    assert changed is False
    user.refresh_from_db()
    assert user.is_staff is True


@pytest.mark.django_db
def test_슈퍼유저_대상에_set_staff_flag를_호출하면_ProtectedAccountError가_발생하고_무변경이다(make_user):
    user = make_user(is_staff=True, is_superuser=True)

    with pytest.raises(services.ProtectedAccountError):
        services.set_staff_flag(user, enabled=False)

    user.refresh_from_db()
    assert user.is_staff is True


@pytest.mark.django_db
def test_활성_대상에_enabled_False로_set_active_flag를_호출하면_비활성화되고_True를_반환한다(make_user):
    user = make_user(is_active=True)

    changed = services.set_active_flag(user, enabled=False)

    assert changed is True
    user.refresh_from_db()
    assert user.is_active is False


@pytest.mark.django_db
def test_이미_활성인_대상에_enabled_True로_set_active_flag를_호출하면_무변경으로_False를_반환한다(make_user):
    user = make_user(is_active=True)

    changed = services.set_active_flag(user, enabled=True)

    assert changed is False
    user.refresh_from_db()
    assert user.is_active is True


@pytest.mark.django_db
def test_슈퍼유저_대상에_set_active_flag를_호출하면_ProtectedAccountError가_발생하고_무변경이다(make_user):
    user = make_user(is_staff=True, is_superuser=True)

    with pytest.raises(services.ProtectedAccountError):
        services.set_active_flag(user, enabled=False)

    user.refresh_from_db()
    assert user.is_active is True
