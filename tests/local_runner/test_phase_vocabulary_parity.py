"""서버 drafts.queries.DISCOVERY_PHASE_LABELS와 러너 local_runner/progress.py의
PHASE_LABELS가 문자 그대로 같은지 지키는 회귀 가드다. local_runner는 drafts를
임포트할 수 없으므로(격리 계약) 러너 쪽은 AST로 딕셔너리 리터럴만 읽는다
(tests/local_runner/test_outcome_vocabulary_parity.py와 같은 방식)."""
import ast
import pathlib

import pytest

from drafts.queries import DISCOVERY_PHASE_LABELS


pytestmark = pytest.mark.contract

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_PROGRESS_PATH = _REPO_ROOT / "local_runner" / "progress.py"


def _extract_phase_labels(source_text):
    tree = ast.parse(source_text)
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "PHASE_LABELS":
                    if isinstance(node.value, ast.Dict):
                        return {
                            key.value: value.value
                            for key, value in zip(node.value.keys, node.value.values)
                            if isinstance(key, ast.Constant) and isinstance(value, ast.Constant)
                        }
    raise AssertionError("PHASE_LABELS dict literal not found")


def test_phase_라벨은_서버와_러너가_문자_그대로_같다():
    runner_labels = _extract_phase_labels(_PROGRESS_PATH.read_text(encoding="utf-8"))
    server_labels = {phase.value: label for phase, label in DISCOVERY_PHASE_LABELS.items()}

    assert runner_labels == server_labels
