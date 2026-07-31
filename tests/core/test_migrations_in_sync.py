"""가드: 모델 변경은 같은 PR에서 마이그레이션까지 함께 나가야 한다.

`makemigrations --check --dry-run`은 모델 필드가 추가·변경됐는데 대응하는
마이그레이션 파일이 없으면 즉시 0이 아닌 코드로 종료한다. 이걸 pytest
단언으로 실행하면 "makemigrations 돌리는 걸 깜빡함"이 배포 때까지 아무도
못 보는 낡은 마이그레이션이 아니라 빠른 스위트 실패가 된다.
"""
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError


pytestmark = pytest.mark.contract


@pytest.mark.django_db
def test_모델_변경사항은_누락된_마이그레이션_없이_동기화되어_있다():
    out = StringIO()
    try:
        call_command(
            "makemigrations",
            "--check",
            "--dry-run",
            stdout=out,
            stderr=out,
        )
    except (CommandError, SystemExit) as exc:
        raise AssertionError(
            "Model changes are missing a migration — run "
            "`python manage.py makemigrations` and commit the result.\n"
            f"{out.getvalue()}"
        ) from exc
