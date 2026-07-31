"""테스트 스위트 자신의 작성 규약 계약.

이 파일은 테스트 스위트가 스스로에게 지키는 계약을 담는다: AGENTS.md의
테스트 작성 정책은 한글로 된 행위 중심 테스트 함수명을 요구하고,
`pytest.ini`는 `--strict-markers`로 등록되지 않은 마커를 오타로 조용히
무시하지 않고 수집 단계에서 거부하게 한다. 둘 다 프로덕션 코드가 아니라
스위트 자체에 대한 구조적 보장이라 `test_architecture_boundaries.py`와
같은 `tests/core` 계약 계층에 두되, 그 파일을 확장하지 않고 전용 파일로
분리했다 — 이름 규약은 그 파일이 다루는 의존성/계층 경계와는 다른 축이고,
이 파일의 AST 순회는 일부러 독립적이라 두 가드는 각자 따로 되돌릴 수
있다. `.docs/plans/2026-07-18-test-suite-stage4-5-plan.md` §4/§8-1 참고.
"""
import ast
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

PROJECT_ROOT = Path(__file__).resolve().parents[2]

_KOREAN_CHAR_RE = re.compile(r"[가-힣]")

# pytest 자체의 수집 패턴(pytest.ini `python_files`)을 그대로 옮겨 왔다 —
# pytest가 실제로 테스트를 수집하는 파일과 정확히 같은 대상을 이 가드가
# 순회하도록.
_TEST_FILE_GLOBS = ("test_*.py", "*_tests.py", "tests.py")


def test_모든_테스트_함수명은_한글_행위명을_포함한다():
    tests_dir = PROJECT_ROOT / "tests"

    test_files = set()
    for pattern in _TEST_FILE_GLOBS:
        test_files.update(tests_dir.glob(f"**/{pattern}"))

    assert test_files, "한글 함수명 가드가 파일을 0건 매칭함 — glob이 깨졌거나 tests가 이동됨"

    violations = []
    for path in sorted(test_files):
        rel_path = path.relative_to(PROJECT_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not node.name.startswith("test_"):
                continue
            if not _KOREAN_CHAR_RE.search(node.name):
                violations.append(f"{rel_path}::{node.name}")

    assert not violations, "\n".join(violations)


def test_pytest_설정은_미등록_마커를_거부하는_strict_markers를_유지한다():
    """`--strict-markers`가 실제로 미등록 마커를 거부하는지는 전체 회귀
    실행 자체가 1차 증거다(수집 단계 에러로 즉시 드러남). 이 테스트는 그
    보호를 켜는 addopts 플래그 자체가 조용히 제거되는 회귀만 별도로
    막는 텍스트 계약이다."""
    pytest_ini = (PROJECT_ROOT / "pytest.ini").read_text(encoding="utf-8")

    assert "--strict-markers" in pytest_ini
