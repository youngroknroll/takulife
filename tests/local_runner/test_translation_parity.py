"""서버(events.content_translation)와 러너(local_runner/translation_flow.py,
local_runner/client.py)가 번역 대상 언어·필드·URL 접두사를 문자 그대로
같게 유지하는지 지키는 동등 가드다. local_runner는 Django·서버 모듈을
임포트할 수 없으므로(tests/local_runner/test_local_runner_isolation.py)
러너 쪽은 AST로 리터럴만 읽는다(tests/local_runner/test_phase_vocabulary_parity.py
·test_outcome_vocabulary_parity.py와 같은 방식). DB는 필요 없다."""

import ast
from pathlib import Path

import pytest
from django.urls import reverse

from events.content_translation import FIELD_MAX_LENGTH, TARGET_LANGUAGES, TRANSLATED_FIELDS


pytestmark = pytest.mark.unit

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TRANSLATION_FLOW_PATH = _REPO_ROOT / "local_runner" / "translation_flow.py"
_CLIENT_PATH = _REPO_ROOT / "local_runner" / "client.py"


def _extract_tuple_literal(source_text, name):
    tree = ast.parse(source_text)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    if isinstance(node.value, ast.Tuple):
                        return tuple(
                            element.value
                            for element in node.value.elts
                            if isinstance(element, ast.Constant)
                        )
    raise AssertionError(f"{name} tuple literal not found in source")


def _extract_string_literal(source_text, name):
    tree = ast.parse(source_text)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == name
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)
                ):
                    return node.value.value
    raise AssertionError(f"{name} string literal not found in source")


def _extract_int_literal(source_text, name):
    tree = ast.parse(source_text)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == name
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, int)
                ):
                    return node.value.value
    raise AssertionError(f"{name} int literal not found in source")


def test_러너와_서버는_번역_대상_언어를_같은_순서로_가진다():
    runner_languages = _extract_tuple_literal(
        _TRANSLATION_FLOW_PATH.read_text(encoding="utf-8"), "TRANSLATION_LANGUAGES"
    )

    assert runner_languages == TARGET_LANGUAGES


def test_러너와_서버는_번역_대상_필드를_같은_순서로_가진다():
    runner_fields = _extract_tuple_literal(
        _TRANSLATION_FLOW_PATH.read_text(encoding="utf-8"), "TRANSLATION_FIELDS"
    )

    assert runner_fields == TRANSLATED_FIELDS


def test_러너_클라이언트의_번역_경로_접두사는_서버_URL과_같다():
    prefix = _extract_string_literal(
        _CLIENT_PATH.read_text(encoding="utf-8"), "_TRANSLATION_URL_PREFIX"
    )

    pending_path = reverse("translation-runner-pending")
    submit_path = reverse("translation-runner-submit")

    assert prefix + "/pending/" == pending_path
    assert prefix + "/submit/" == submit_path


def test_러너의_입력_절단_상한은_서버_번역_필드_최대_길이의_두_배다():
    runner_limit = _extract_int_literal(
        _TRANSLATION_FLOW_PATH.read_text(encoding="utf-8"), "TRANSLATION_INPUT_MAX_CHARS"
    )

    assert runner_limit == 2 * max(FIELD_MAX_LENGTH.values())
