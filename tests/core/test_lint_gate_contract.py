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
# 설정 키 집합을 고정한다. 새 키(예: lint.ignore)가 조용히 들어오는 것을 막는다.
ALLOWED_RUFF_KEYS = {"line-length", "extend-exclude", "lint"}
ALLOWED_RUFF_LINT_KEYS = {"select", "per-file-ignores", "isort", "flake8-tidy-imports"}
KEY_CHANGE_HINT = "의도한 변경이면 이 테스트의 허용 키를 함께 고친다"
# 하위 설정 파일 탐색에서 건너뛰는 폴더
SKIPPED_PARTS = {".venv", "venv", ".git", "node_modules", ".ruff_cache", ".pytest_cache"}


def _find_nested_ruff_configs() -> list[str]:
    """루트 설정을 덮어쓸 수 있는 하위 ruff 설정 파일을 찾는다."""
    found = []
    for path in PROJECT_ROOT.rglob("*"):
        relative = path.relative_to(PROJECT_ROOT)
        if SKIPPED_PARTS & set(relative.parts) or not path.is_file():
            continue
        if path.name in {"ruff.toml", ".ruff.toml"}:
            found.append(str(relative))
        elif path.name == "pyproject.toml" and relative.parent != Path("."):
            with path.open("rb") as f:
                if "ruff" in tomllib.load(f).get("tool", {}):
                    found.append(str(relative))
    return found


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

    assert set(ruff) == ALLOWED_RUFF_KEYS, (
        f"[tool.ruff] 키가 허용 집합과 다르다: {sorted(ruff)}. {KEY_CHANGE_HINT}"
    )
    assert set(ruff["lint"]) == ALLOWED_RUFF_LINT_KEYS, (
        f"[tool.ruff.lint] 키가 허용 집합과 다르다: {sorted(ruff['lint'])}. {KEY_CHANGE_HINT}"
    )
    assert ruff["extend-exclude"] == ["**/migrations/**"], (
        "[tool.ruff] extend-exclude가 마이그레이션 제외 하나가 아니다"
    )
    assert ruff["lint"]["per-file-ignores"] == {"tests/**": ["E501"]}, (
        "per-file-ignores가 tests의 E501 면제 하나가 아니다"
    )

    nested = _find_nested_ruff_configs()
    assert not nested, f"루트 설정을 덮어쓸 수 있는 하위 ruff 설정이 있다: {nested}"


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


def _pull_request_trigger_keys(triggers: str) -> dict[str, str]:
    """트리거 영역에서 `pull_request:` 아래 더 깊이 들여쓴 줄의 키와 값을 모은다(주석 제외)."""
    header = re.search(r"^(\s*)pull_request:[ \t]*$", triggers, re.MULTILINE)
    if header is None:
        return {}
    base_indent = len(header.group(1))
    keys = {}
    for line in triggers[header.end() :].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if len(line) - len(line.lstrip()) <= base_indent:
            break
        match = re.match(r"^\s+([a-z-]+):\s*(.*)$", line)
        if match:
            keys[match.group(1)] = match.group(2).strip()
    return keys


def test_CI_워크플로는_린트_잡에서_ruff_check와_ruff_format_check를_uv_run으로_실행한다():
    """린트 잡이 존재하고, ruff 두 명령을 uv run으로 실행하며, 관측 모드로 약해지지 않는다."""
    workflow_text = (PROJECT_ROOT / ".github/workflows/ci.yml").read_text()

    block = _find_job_block(workflow_text, LINT_JOB_NAME)
    assert block is not None, f"ci.yml에 '{LINT_JOB_NAME}' 잡이 없다"

    assert re.search(r"^\s+run:\s*uv run ruff check \.\s*$", block, re.MULTILINE), (
        "린트 잡에 'run: uv run ruff check .' 줄이 정확히 일치하는 단계가 없다"
    )
    assert re.search(r"^\s+run:\s*uv run ruff format --check \.\s*$", block, re.MULTILINE), (
        "린트 잡에 'run: uv run ruff format --check .' 줄이 정확히 일치하는 단계가 없다"
    )
    for bypass in ("|| true", "|| exit 0", "--exit-zero"):
        assert bypass not in block, f"린트 잡에 실패를 무시하는 '{bypass}'가 있다"
    assert re.search(r"^\s*(?:-\s+)?if:", block, re.MULTILINE) is None, (
        "린트 잡 또는 단계에 if: 조건이 있다 (조건부로 건너뛰면 PR 게이트가 아니다)"
    )
    assert re.search(r"^\s*needs:", block, re.MULTILINE) is None, (
        "린트 잡에 needs:가 있다 (다른 잡이 건너뛰면 린트도 skipped가 된다)"
    )
    triggers = workflow_text.partition("\njobs:\n")[0]
    assert _pull_request_trigger_keys(triggers) == {"branches-ignore": "[production]"}, (
        "ci.yml pull_request 트리거가 branches-ignore: [production] 하나가 아니다 "
        "(paths-ignore 등으로 PR 실행 자체가 빠질 수 있다)"
    )
    assert re.search(r"^\s+pull_request:", triggers, re.MULTILINE), (
        "ci.yml 트리거에 pull_request가 없다 (PR 게이트가 아니게 된다)"
    )
    assert "continue-on-error" not in block, (
        "린트 잡에 continue-on-error가 있다 (관측 모드로 약해지면 PR 게이트가 아니다)"
    )
    assert "python3 -c" not in block, "린트 잡에 'python3 -c'가 있다 (uv run python -c를 써야 한다)"
