"""The test suite's own authoring-policy contracts.

This file owns the test suite's contract with itself: AGENTS.md's Test
Authoring Policy requires Korean, behavior-centered test function names, and
`pytest.ini` relies on `--strict-markers` to reject an unregistered marker at
collection time instead of silently ignoring a typo. Both are structural
guarantees about the suite, not about production code, so they live next to
`test_architecture_boundaries.py` (same `tests/core` contract layer) but in a
dedicated file rather than an extension of it — naming policy is a different
axis from the dependency/layer boundaries that file owns, and this file's AST
walk is deliberately independent so either guard can be rolled back on its
own. See `.docs/plans/2026-07-18-test-suite-stage4-5-plan.md` §4/§8-1.
"""
import ast
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

PROJECT_ROOT = Path(__file__).resolve().parents[2]

_KOREAN_CHAR_RE = re.compile(r"[가-힣]")

# pytest's own collection patterns (pytest.ini `python_files`); mirrored here
# so this guard walks exactly the files pytest itself would collect tests
# from.
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
