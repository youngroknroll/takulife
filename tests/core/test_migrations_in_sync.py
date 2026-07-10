"""Guard: model changes must ship their migration in the same PR.

`makemigrations --check --dry-run` exits non-zero the moment a model field
is added/changed without a matching migration file. Running it as a pytest
assertion turns "forgot to run makemigrations" into a fast-suite failure
instead of a stale migration nobody notices until deploy.
"""
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError


@pytest.mark.django_db
def test_no_missing_migrations():
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
