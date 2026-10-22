"""ci.yml의 pull_request 트리거 조건을 텍스트로 검증한다.
이 테스트는 ci.yml 텍스트 계약만 증명하고, GitHub이 실제로 실행을 건너뛰는지는
PR·머지 후 실행 기록으로 확인한다.
"""
from pathlib import Path
import re


def _slice_on_block(workflow_text: str) -> str:
    # on: 다음 줄부터, 들여쓰기 없는(최상위) 다음 줄 직전까지가 on 블록이다.
    match = re.search(r"^on:\n(.*?)(?=^\S|\Z)", workflow_text, re.M | re.S)
    assert match is not None, "ci.yml에 on: 블록이 없다"
    return match.group(1)


def _slice_pull_request_block(on_block: str) -> str:
    # pull_request: 다음 줄부터, 같은 들여쓰기(2칸)의 다음 키 직전까지가 블록이다.
    match = re.search(
        r"^  pull_request:\n(.*?)(?=^  \S|\Z)", on_block, re.M | re.S
    )
    assert match is not None, "on: 블록에 pull_request: 키가 없다"
    return match.group(1)


def _strip_comment_lines(block_text: str) -> str:
    # 주석 줄은 판정에서 제외해, 주석에 적힌 문자열로 우연히 통과하지 않게 한다.
    return "\n".join(
        line for line in block_text.splitlines() if not line.strip().startswith("#")
    )


def test_CI_워크플로가_production을_향한_PR에서는_pull_request_트리거를_건너뛴다():
    workflow_path = (
        Path(__file__).resolve().parents[2] / ".github/workflows/ci.yml"
    )
    workflow_text = workflow_path.read_text()

    on_block = _slice_on_block(workflow_text)
    pull_request_block = _slice_pull_request_block(on_block)
    judged_text = _strip_comment_lines(pull_request_block)

    assert "branches-ignore" in judged_text, (
        "pull_request 트리거에 branches-ignore 조건이 없다"
    )
    assert "production" in judged_text, (
        "pull_request의 branches-ignore 목록에 production이 없다"
    )
