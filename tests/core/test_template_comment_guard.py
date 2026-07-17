"""Guard: Django `{# ... #}` inline comments must open and close on the same
line.

Django's template tokenizer matches `{# ... #}` with a regex that does not
span newlines — a comment opened on one line and closed on a later line is
never recognized as a comment token at all, so everything from `{#` to `#}`
(inclusive) renders as literal page text instead of being stripped. Confirmed
in a real browser on the staff event-edit page before this guard was added.
Multi-line comments must use `{% comment %}...{% endcomment %}` instead.

Scan scope: only the project-level templates/ dir. APP_DIRS=True means an
app-local <app>/templates/ would also be eligible for template resolution
(none exist today) — this guard would need extending if one appears.

Heuristic limits: a plain text scan that does not distinguish
script/style/verbatim contexts, and a line that both closes and reopens a
comment (e.g. "... #} text {# ...") is not individually enumerated in the
violation list — but any file containing one still fails the assertion.
"""
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEMPLATES_ROOT = PROJECT_ROOT / "templates"


def _unbalanced_comment_lines():
    violations = []
    for path in sorted(TEMPLATES_ROOT.rglob("*.html")):
        for lineno, line in enumerate(path.read_text().splitlines(), start=1):
            if line.count("{#") > line.count("#}"):
                violations.append(f"{path.relative_to(PROJECT_ROOT)}:{lineno}")
    return violations


def test_템플릿에_여러_줄에_걸친_django_주석이_없다():
    violations = _unbalanced_comment_lines()

    assert not violations, violations
