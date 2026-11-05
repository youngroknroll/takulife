"""트랙 43-3 슬라이스 8: 컬렉션·활동·아카이브·계정 뷰, 아카이브 서비스·
시리얼라이저·API 뷰, 공용 어휘 코드의 한국어 문자열은 번역 함수의 인자이거나
독스트링·로그·스키마 문서 인자여야 한다. 나머지 한국어 문자열은 번역 누락이다.
`web/views/events.py`는 `test_ui_korean_literal_guard.py`의 기존 가드가 맡는다."""

import ast
from pathlib import Path
import re

import pytest

pytestmark = pytest.mark.contract

PROJECT_ROOT = Path(__file__).resolve().parents[2]

_TARGET_RELPATHS = [
    "web/views/collection.py",
    "web/views/activity.py",
    "web/views/archive.py",
    "web/views/account.py",
    "archive/services.py",
    "archive/serializers.py",
    "archive/views.py",
    "core/vocab.py",
]

_KOREAN_RE = re.compile(r"[가-힣]")

_GETTEXT_FUNCTION_NAMES = frozenset(
    {
        "gettext",
        "gettext_lazy",
        "gettext_noop",
        "ngettext",
        "ngettext_lazy",
        "npgettext",
        "npgettext_lazy",
        "pgettext",
        "pgettext_lazy",
        "_",
    }
)

# 호출 인자 전체(위치·키워드·중첩)를 면제하는 호출 이름.
_SCHEMA_DOC_FUNCTION_NAMES = frozenset(
    {
        "extend_schema",
        "extend_schema_view",
        "OpenApiResponse",
        "OpenApiParameter",
        "OpenApiExample",
    }
)
_SCHEMA_DOC_PATHS = frozenset({"archive/views.py"})

# 스태프 콘솔 전용 상수는 번역 대상이 아니다(스태프 화면은 한국어 고정).
_STAFF_ONLY_CONSTANTS = {"core/vocab.py": frozenset({"STAFF_EVENT_SORT"})}


def _called_function_name(call):
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _is_logging_call(call):
    """`logger.info(...)`·`logging.warning(...)`처럼 로거 객체의 메서드 호출."""
    func = call.func
    return (
        isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Name)
        and func.value.id in {"logger", "logging", "log"}
    )


def _constants_under(node):
    return [
        child
        for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    ]


def _exempt_string_nodes(tree, relpath):
    """독스트링, 번역 함수의 문자열 위치 인자, 로깅 호출 인자, (archive/views.py의)
    drf-spectacular 호출 인자, 스태프 전용 상수 값을 검사에서 뺀다."""
    exempt = set()
    staff_names = _STAFF_ONLY_CONSTANTS.get(relpath, frozenset())
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                exempt.add(id(body[0].value))
        if isinstance(node, ast.Call):
            name = _called_function_name(node)
            if name in _GETTEXT_FUNCTION_NAMES:
                for arg in node.args:
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        exempt.add(id(arg))
            elif _is_logging_call(node):
                exempt.update(id(c) for c in _constants_under(node))
            elif relpath in _SCHEMA_DOC_PATHS and name in _SCHEMA_DOC_FUNCTION_NAMES:
                exempt.update(id(c) for c in _constants_under(node))
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if node.value is not None and any(
                isinstance(t, ast.Name) and t.id in staff_names for t in targets
            ):
                exempt.update(id(c) for c in _constants_under(node.value))
    return exempt


def _violations(relpath):
    tree = ast.parse((PROJECT_ROOT / relpath).read_text(encoding="utf-8"))
    exempt = _exempt_string_nodes(tree, relpath)
    return [
        f"{relpath}:{node.lineno} {node.value.strip()[:40]!r}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in exempt
        and _KOREAN_RE.search(node.value)
    ]


def test_가드_대상_파이썬_파일은_8개이고_모두_존재한다():
    assert len(_TARGET_RELPATHS) == 8
    assert [p for p in _TARGET_RELPATHS if not (PROJECT_ROOT / p).is_file()] == []


def test_컬렉션_활동_아카이브_계정_코드에는_번역_함수_밖의_한국어_문자열_상수가_없다():
    violations = [v for relpath in _TARGET_RELPATHS for v in _violations(relpath)]

    assert violations == []
