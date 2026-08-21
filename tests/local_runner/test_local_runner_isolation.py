"""local_runner 패키지 격리 계약(CT2) — tests/core/test_architecture_boundaries.py의
_imported_modules와 같은 AST 파싱 방식을 여기서도 그대로 쓴다(패키지가 이 세션 시점에
아직 없어 공유 임포트는 하지 않는다)."""
import ast
from pathlib import Path

import pytest


pytestmark = pytest.mark.contract

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 서버 도메인 모듈과 Django. httpx·표준 라이브러리만 허용한다.
_FORBIDDEN_MODULES = {"django", "drafts", "events", "archive", "staff", "core", "config"}


def _imported_module_names(path):
    tree = ast.parse(path.read_text())
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.level:
                continue
            modules.add(node.module)
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    return modules


def test_local_runner_패키지는_django와_서버_도메인_모듈을_임포트하지_않는다():
    local_runner_dir = PROJECT_ROOT / "local_runner"

    # 러너는 DB 자격 없는 최소 권한 클라이언트라는 정본 계약 — 서버 도메인·Django에 무의존.
    assert local_runner_dir.is_dir()

    violations = {}
    for path in sorted(local_runner_dir.rglob("*.py")):
        modules = _imported_module_names(path)
        forbidden = {
            module
            for module in modules
            if any(module == app or module.startswith(f"{app}.") for app in _FORBIDDEN_MODULES)
        }
        if forbidden:
            violations[str(path.relative_to(PROJECT_ROOT))] = forbidden

    assert not violations, violations
