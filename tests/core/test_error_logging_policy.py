"""오류 처리·로깅 정책을 강제하는 AST 계약 가드.

`AGENTS.md`의 Error Handling And Logging 절이 정한 규칙을 이 파일이 기계적으로
검사한다 — 맨 `except:` 금지, catch-all 핸들러는 예외를 삼키는 이유를 반드시
드러낼 것(로깅, 재발생, `# except-ok: <이유>` 마커 중 하나), 프로덕션 코드에
떠돌이 `print()` 금지, 모듈 로거는 영어 ASCII·지연 평가되는 `%` 형식의 첫
인자를 쓸 것, `logging.getLogger`는 항상 `__name__`으로만 호출할 것. 아래
6개 함수가 각각 하나의 결정적 규칙(EHL-01~06)을 구현한다.

스캔 범위는 `test_test_authoring_policy.py`의 파일 순회 방식과 같다 —
프로덕션 패키지 아래 모든 `*.py`, `migrations/`는 제외(자동 생성이라
사람이 직접 쓴 코드가 아님).

아래 검사 중 두 개(메시지 ASCII 여부 / 첫 인자가 상수인지)는 먼저 어떤
이름이 실제 로거인지 가려내야 한다 — 메서드명만 보고 매칭하면(예:
`.error(...)`) 사용자에게 보이는 한국어 텍스트인 `messages.error(request,
"...")` 호출까지 걸려 이 정책의 대상 밖을 침범한다. `_logger_target_names`가
파일마다 먼저 AST를 훑어 `X = logging.getLogger(...)` 대입 대상을 모으고,
그 이름에 대한 호출만 로거 호출로 센다.
"""
import ast
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

PROJECT_ROOT = Path(__file__).resolve().parents[2]

_SCAN_PACKAGES = ("accounts", "archive", "config", "core", "drafts", "events", "staff", "web", "local_runner")

_LOGGER_METHODS = {"debug", "info", "warning", "error", "exception", "critical"}

_EXCEPT_OK_MARKER_RE = re.compile(r"#\s*except-ok:\s*\S")


def _production_python_files():
    files = []
    for package in _SCAN_PACKAGES:
        for path in sorted((PROJECT_ROOT / package).rglob("*.py")):
            if "migrations" in path.relative_to(PROJECT_ROOT).parts:
                continue
            files.append(path)
    return files


def _rel(path):
    return path.relative_to(PROJECT_ROOT).as_posix()


def _parse(path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _is_catch_all_handler(handler):
    if handler.type is None:
        return True
    return isinstance(handler.type, ast.Name) and handler.type.id == "Exception"


def _handler_has_logger_exception_call(handler):
    for node in ast.walk(handler):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "exception"
        ):
            return True
    return False


def _handler_has_raise(handler):
    for node in ast.walk(handler):
        if isinstance(node, ast.Raise):
            return True
    return False


def _handler_has_except_ok_marker(source_lines, handler):
    start = handler.lineno
    end = getattr(handler.body[-1], "end_lineno", None) or handler.body[-1].lineno
    for lineno in range(start, end + 1):
        line = source_lines[lineno - 1]
        if _EXCEPT_OK_MARKER_RE.search(line):
            return True
    return False


def _logger_target_names(tree):
    """모듈 어디선가 `logging.getLogger(...)`가 대입된 이름들 — 이 집합에
    있어야 나중의 `<name>.error(...)`가 `messages.error(...)`가 아니라
    로거 호출로 인정된다."""
    names = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        value = node.value
        if not (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Attribute)
            and value.func.attr == "getLogger"
            and isinstance(value.func.value, ast.Name)
            and value.func.value.id == "logging"
        ):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name):
                names.add(target.id)
    return names


def _logger_calls(tree, logger_names):
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if (
            isinstance(func, ast.Attribute)
            and func.attr in _LOGGER_METHODS
            and isinstance(func.value, ast.Name)
            and func.value.id in logger_names
        ):
            calls.append(node)
    return calls


def test_프로덕션_코드에_bare_except가_없다():
    violations = []
    for path in _production_python_files():
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                violations.append(f"{_rel(path)}:{node.lineno}")

    assert not violations, "\n".join(violations)


def test_catch_all_블록은_로깅이나_재발생이나_명시적_마커_중_하나를_가진다():
    violations = []
    for path in _production_python_files():
        tree = _parse(path)
        source_lines = path.read_text(encoding="utf-8").splitlines()
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if not _is_catch_all_handler(node):
                continue
            if _handler_has_logger_exception_call(node):
                continue
            if _handler_has_raise(node):
                continue
            if _handler_has_except_ok_marker(source_lines, node):
                continue
            violations.append(f"{_rel(path)}:{node.lineno}")

    assert not violations, "\n".join(violations)


def test_프로덕션_코드에_print_호출이_없다():
    violations = []
    for path in _production_python_files():
        tree = _parse(path)
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "print"
            ):
                violations.append(f"{_rel(path)}:{node.lineno}")

    assert not violations, "\n".join(violations)


def test_로거_메시지_리터럴은_영어_ASCII다():
    violations = []
    for path in _production_python_files():
        tree = _parse(path)
        logger_names = _logger_target_names(tree)
        if not logger_names:
            continue
        for call in _logger_calls(tree, logger_names):
            if not call.args:
                continue
            first_arg = call.args[0]
            if not (isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str)):
                continue
            if not first_arg.value.isascii():
                violations.append(f"{_rel(path)}:{call.lineno}")

    assert not violations, "\n".join(violations)


def test_로거_호출의_첫_인자는_문자열_상수다():
    violations = []
    for path in _production_python_files():
        tree = _parse(path)
        logger_names = _logger_target_names(tree)
        if not logger_names:
            continue
        for call in _logger_calls(tree, logger_names):
            if not call.args:
                violations.append(f"{_rel(path)}:{call.lineno}")
                continue
            first_arg = call.args[0]
            if not (isinstance(first_arg, ast.Constant) and isinstance(first_arg.value, str)):
                violations.append(f"{_rel(path)}:{call.lineno}")

    assert not violations, "\n".join(violations)


def test_모듈_로거는_모듈명으로만_생성한다():
    violations = []
    for path in _production_python_files():
        tree = _parse(path)
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "getLogger"
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "logging"
            ):
                continue
            is_name_dunder_arg_only = (
                len(node.args) == 1
                and isinstance(node.args[0], ast.Name)
                and node.args[0].id == "__name__"
                and not node.keywords
            )
            if not is_name_dunder_arg_only:
                violations.append(f"{_rel(path)}:{node.lineno}")

    assert not violations, "\n".join(violations)
