"""러너가 event_outcomes에 실제로 낼 수 있는 (outcome, reason) 짝이 서버
허용목록(drafts.discovery_runs.EVENT_OUTCOME_REASONS)을 벗어나지 않는지
지키는 회귀 가드다. local_runner/exploration_flow.py 소스를 AST로 읽어
_record_outcome 호출의 리터럴 인자를 추출한다 — drafts는 임포트하지 않는
local_runner 패키지의 계약을 지키려는 것이라, 러너 쪽은 텍스트/AST로만
다룬다."""
import ast
import pathlib

import pytest

from drafts.discovery_runs import EVENT_OUTCOME_REASONS


pytestmark = pytest.mark.contract

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_RUNNER_PATH = _REPO_ROOT / "local_runner" / "exploration_flow.py"


def _extract_server_excluded_reason_values(tree):
    """_SERVER_EXCLUDED_REASONS = {...} 딕셔너리 리터럴의 값들을 그대로 읽는다."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "_SERVER_EXCLUDED_REASONS":
                    if isinstance(node.value, ast.Dict):
                        return {
                            value.value
                            for value in node.value.values
                            if isinstance(value, ast.Constant) and isinstance(value.value, str)
                        }
    raise AssertionError("_SERVER_EXCLUDED_REASONS dict literal not found")


def _extract_outcome_reason_pairs(source_text):
    """_record_outcome(... outcome=X, reason=Y) 호출을 전부 찾아 실제로 낼 수
    있는 (outcome, reason) 짝 전체를 집합으로 돌려준다. 값이 리터럴이 아닌
    두 곳은 코드를 직접 대조해 낼 수 있는 값을 명시했다:
    - reason=reason: caption_interpreter.exclusion_reason()이 내는 값은
      "overseas"·"ended" 둘뿐이다(drafts.agent_drafts._exclusion_reason과
      같은 계약).
    - outcome=response["status"]: 바로 위 가드
      `response.get("status") in ("created", "duplicate")`가 이미 두 값으로
      제한해 뒀다.
    - reason=server_reason: 같은 파일의 _SERVER_EXCLUDED_REASONS 딕셔너리
      값이 실제로 나올 수 있는 값이다(AST로 추출, 지어내지 않는다)."""
    tree = ast.parse(source_text)
    server_excluded_reason_values = _extract_server_excluded_reason_values(tree)

    pairs = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id != "_record_outcome":
            continue

        keywords = {keyword.arg: keyword.value for keyword in node.keywords}
        outcome_node = keywords.get("outcome")
        reason_node = keywords.get("reason")

        if isinstance(outcome_node, ast.Constant) and isinstance(outcome_node.value, str):
            outcome_values = {outcome_node.value}
        elif isinstance(outcome_node, ast.Subscript):
            outcome_values = {"created", "duplicate"}
        else:
            raise AssertionError(f"unhandled outcome argument shape: {ast.dump(outcome_node)}")

        if isinstance(reason_node, ast.Constant) and isinstance(reason_node.value, str):
            reason_values = {reason_node.value}
        elif isinstance(reason_node, ast.Name) and reason_node.id == "reason":
            reason_values = {"overseas", "ended"}
        elif isinstance(reason_node, ast.Name) and reason_node.id == "server_reason":
            reason_values = set(server_excluded_reason_values)
        else:
            raise AssertionError(f"unhandled reason argument shape: {ast.dump(reason_node)}")

        for outcome_value in outcome_values:
            for reason_value in reason_values:
                pairs.add((outcome_value, reason_value))

    return pairs


def test_러너가_내는_결과와_사유는_모두_서버_허용목록에_있다():
    pairs = _extract_outcome_reason_pairs(_RUNNER_PATH.read_text(encoding="utf-8"))

    # 추출이 조용히 비어 버리면(호출 이름이 바뀌는 등) 통과가 가짜 통과가
    # 된다 — 실제 호출 지점 수(11곳)보다 적을 수 없다.
    assert len(pairs) >= 11

    for outcome, reason in sorted(pairs):
        allowed_reasons = EVENT_OUTCOME_REASONS.get(outcome)
        assert allowed_reasons is not None, f"서버 허용목록에 없는 outcome: {outcome!r}"
        assert reason in allowed_reasons, (
            f"서버 허용목록에 없는 (outcome, reason) 짝: ({outcome!r}, {reason!r})"
        )
