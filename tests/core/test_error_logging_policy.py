"""AST contract guards for the error-handling/logging policy.

`AGENTS.md`'s Error Handling And Logging section documents the live rules this
file enforces mechanically: no bare `except:`, every catch-all handler is
explicit about why it swallows the exception (log, re-raise, or a
`# except-ok: <reason>` marker), no stray `print()` in production code,
module loggers are English-ASCII with lazy `%`-style first arguments, and
`logging.getLogger` is only ever called with `__name__`. These six functions
implement one deterministic contract each (EHL-01..EHL-06).

Scan scope mirrors `test_test_authoring_policy.py`'s file-walk style: every
`*.py` under the production packages, `migrations/` excluded (generated,
not hand-authored).

Two of the checks below (message ASCII / first-arg-is-constant) must first
resolve which names are actually loggers — a bare method-name match (e.g.
`.error(...)`) would also catch `messages.error(request, "...")` calls,
which are user-facing Korean text explicitly out of this policy's scope.
`_logger_target_names` does a first AST pass
per file collecting `X = logging.getLogger(...)` assignment targets; only
calls on those names count as logger calls.
"""
import ast
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

PROJECT_ROOT = Path(__file__).resolve().parents[2]

_SCAN_PACKAGES = ("accounts", "archive", "config", "core", "drafts", "events", "staff")

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
    """Names assigned `logging.getLogger(...)` at any point in the module —
    the receiver set that makes a later `<name>.error(...)` a logger call
    rather than, say, `messages.error(...)`."""
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
