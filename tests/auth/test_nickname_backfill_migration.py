"""닉네임 백필 RunPython(accounts.migrations.0006_user_nickname.backfill_nickname)
테스트. 0006이 컬럼을 곧 대소문자 무시 UNIQUE로 만들기 때문에 CP10 방식(현재
스키마에 NULL 행을 만들어 함수만 호출)이 성립하지 않는 경우는
MigrationExecutor로 실제 0005→0006 이주를 돌려 검증한다."""
import importlib

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

pytestmark = pytest.mark.contract


def _migrate_to(target):
    executor = MigrationExecutor(connection)
    executor.migrate(target)
    return executor.loader.project_state(target).apps


@pytest.mark.django_db(transaction=True)
def test_백필_실행시_모든_기존_회원에_회원pk_닉네임이_채워진다():
    old_apps = _migrate_to([("accounts", "0005_user_password_changed_at")])
    OldUser = old_apps.get_model("accounts", "User")
    first = OldUser.objects.create(email="nick-a@example.com", password="")
    second = OldUser.objects.create(email="nick-b@example.com", password="")

    new_apps = _migrate_to([("accounts", "0006_user_nickname")])
    NewUser = new_apps.get_model("accounts", "User")

    assert NewUser.objects.get(pk=first.pk).nickname == f"회원{first.pk}"
    assert NewUser.objects.get(pk=second.pk).nickname == f"회원{second.pk}"


@pytest.mark.django_db(transaction=True)
def test_유예_탈퇴_중_계정도_백필_대상이다():
    old_apps = _migrate_to([("accounts", "0005_user_password_changed_at")])
    OldUser = old_apps.get_model("accounts", "User")
    pending = OldUser.objects.create(
        email="nick-pending@example.com",
        password="",
        deletion_requested_at=timezone.now(),
    )

    new_apps = _migrate_to([("accounts", "0006_user_nickname")])
    NewUser = new_apps.get_model("accounts", "User")

    assert NewUser.objects.get(pk=pending.pk).nickname == f"회원{pending.pk}"


@pytest.mark.django_db(transaction=True)
def test_빈_DB에서_백필은_예외_없이_통과한다():
    _migrate_to([("accounts", "0005_user_password_changed_at")])

    new_apps = _migrate_to([("accounts", "0006_user_nickname")])
    NewUser = new_apps.get_model("accounts", "User")

    assert NewUser.objects.count() == 0


@pytest.mark.django_db
def test_백필은_이미_닉네임이_있는_행을_덮어쓰지_않는다(make_user):
    from django.apps import apps as real_apps

    user = make_user(nickname="타쿠")

    module = importlib.import_module("accounts.migrations.0006_user_nickname")
    module.backfill_nickname(real_apps, None)

    user.refresh_from_db()
    assert user.nickname == "타쿠"
