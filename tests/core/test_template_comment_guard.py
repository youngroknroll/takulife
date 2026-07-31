"""가드: Django `{# ... #}` 한 줄 주석은 같은 줄에서 열고 닫아야 한다.

Django 템플릿 토크나이저는 `{# ... #}`를 줄바꿈을 넘지 않는 정규식으로
매칭한다 — 한 줄에서 열고 다른 줄에서 닫은 주석은 주석 토큰으로 아예
인식되지 않아, `{#`부터 `#}`까지(포함) 전부 제거되지 않고 페이지에 그대로
글자로 새어 나온다. 이 가드를 만들기 전 스태프 행사수정 페이지에서 실제
브라우저로 확인된 현상이다. 여러 줄 주석은 반드시 `{% comment %}...{%
endcomment %}`를 써야 한다.

스캔 범위: 프로젝트 레벨 templates/ 디렉터리만. APP_DIRS=True라 앱별
<app>/templates/도 템플릿 해석 대상이 될 수 있지만(현재는 없음) 그런
디렉터리가 생기면 이 가드도 넓혀야 한다.

한계: script/style/verbatim 맥락을 구분하지 않는 단순 텍스트 스캔이고,
한 줄에서 주석을 닫고 다시 여는 경우(예: "... #} 텍스트 {# ...")는
위반 목록에 개별적으로 나열되지 않는다 — 다만 그런 줄이 있는 파일은
여전히 검증에서 실패한다.
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
