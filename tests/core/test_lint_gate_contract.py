"""린트 설정 계약.

`pyproject.toml`의 `[tool.ruff]`는 텍스트 설정이라 실행으로는 확인할 수 없다.
린트 기준이 조용히 느슨해지는 변경을 막는다.
또한 CI 워크플로의 린트 잡 계약(.github/workflows/ci.yml 텍스트)도 함께 다룬다.
"""

from pathlib import Path
import re
import tomllib

import pytest

pytestmark = pytest.mark.contract

PROJECT_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_LINE_LENGTH = 100
# 이 규칙들은 반드시 켜져 있어야 하며, 다른 규칙이 더 있어도 된다.
REQUIRED_RULES = {"E4", "E7", "E9", "E501", "W", "F", "I", "B006", "TID252"}


def test_린트_설정은_줄_길이_100칸과_필수_규칙_집합을_유지한다():
    """줄 길이, 필수 규칙 집합, 상대 임포트 금지가 유지되어야 한다."""
    with (PROJECT_ROOT / "pyproject.toml").open("rb") as f:
        pyproject = tomllib.load(f)

    assert "ruff" in pyproject.get("tool", {}), "pyproject.toml에 [tool.ruff] 섹션이 없다"
    ruff = pyproject["tool"]["ruff"]

    assert ruff.get("line-length") == REQUIRED_LINE_LENGTH, (
        f"[tool.ruff] line-length가 {REQUIRED_LINE_LENGTH}이 아니다"
    )

    selected = set(ruff.get("lint", {}).get("select", []))
    missing = REQUIRED_RULES - selected
    assert not missing, f"[tool.ruff.lint] select에 필수 규칙이 빠졌다: {sorted(missing)}"

    ban = ruff.get("lint", {}).get("flake8-tidy-imports", {}).get("ban-relative-imports")
    assert ban == "all", "flake8-tidy-imports ban-relative-imports가 'all'이 아니다"


LINT_JOB_NAME = "Lint and format (PR gate)"
JOB_KEY_PATTERN = re.compile(r"^  [A-Za-z0-9_-]+:[ \t]*$", re.MULTILINE)


def _find_job_block(workflow_text: str, job_name: str) -> str | None:
    """`jobs:` 아래에서 `name:` 값이 job_name인 잡 블록(잡 키 줄부터 다음 잡 키 직전)을 돌려준다."""
    _, separator, jobs_text = workflow_text.partition("\njobs:\n")
    if not separator:
        return None
    keys = list(JOB_KEY_PATTERN.finditer(jobs_text))
    for index, key in enumerate(keys):
        end = keys[index + 1].start() if index + 1 < len(keys) else len(jobs_text)
        block = jobs_text[key.start() : end]
        if re.search(rf"^    name:\s*{re.escape(job_name)}\s*$", block, re.MULTILINE):
            return block
    return None


def test_CI_워크플로는_린트_잡에서_ruff_check와_ruff_format_check를_uv_run으로_실행한다():
    """린트 잡이 존재하고, ruff 두 명령을 uv run으로 실행하며, 관측 모드로 약해지지 않는다."""
    workflow_text = (PROJECT_ROOT / ".github/workflows/ci.yml").read_text()

    block = _find_job_block(workflow_text, LINT_JOB_NAME)
    assert block is not None, f"ci.yml에 '{LINT_JOB_NAME}' 잡이 없다"

    assert "uv run ruff check ." in block, "린트 잡에 'uv run ruff check .' 단계가 없다"
    assert "uv run ruff format --check ." in block, (
        "린트 잡에 'uv run ruff format --check .' 단계가 없다"
    )
    assert "continue-on-error" not in block, (
        "린트 잡에 continue-on-error가 있다 (관측 모드로 약해지면 PR 게이트가 아니다)"
    )
    assert "python3 -c" not in block, "린트 잡에 'python3 -c'가 있다 (uv run python -c를 써야 한다)"
