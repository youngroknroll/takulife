"""린트 설정 계약.

`pyproject.toml`의 `[tool.ruff]`는 텍스트 설정이라 실행으로는 확인할 수 없다.
린트 기준이 조용히 느슨해지는 변경을 막는다.
"""

import tomllib
from pathlib import Path

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
