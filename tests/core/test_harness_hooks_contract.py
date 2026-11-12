"""`.claude/hooks/`의 PreToolUse 훅 4개가 명령 형태를 올바르게 판정하는지 검증한다.

AGENTS.md "Harness Enforcement (hooks)"가 정본이며, 이 파일은 그 표의 차단/허용
목록을 실제 서브프로세스 실행으로 고정한다. 선례는
tests/core/test_run_runner_wrapper_contract.py.
"""

import json
from pathlib import Path
import subprocess

import pytest

pytestmark = pytest.mark.contract

PROJECT_ROOT = Path(__file__).resolve().parents[2]
UV_ONLY_GUARD = PROJECT_ROOT / ".claude/hooks/uv-only-guard.sh"
GIT_STAGE_ALL_GUARD = PROJECT_ROOT / ".claude/hooks/git-stage-all-guard.sh"
PLAN_BASH_WRITE_GUARD = PROJECT_ROOT / ".claude/hooks/plan-bash-write-guard.sh"
GIT_DESTRUCTIVE_GUARD = PROJECT_ROOT / ".claude/hooks/git-destructive-guard.sh"

ALLOW = 0
BLOCK = 2


def _run_hook(hook_path, command, cwd):
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": command},
        "cwd": str(cwd),
    }
    return subprocess.run(
        [str(hook_path)],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        cwd=cwd,
        timeout=10,
    )


UV_ONLY_CASES = [
    # 회귀: 기존에 올바르게 판정되던 형태.
    ("공백_구분_pytest_단독_실행은_차단된다", "pytest -q", BLOCK),
    ("pip_install은_차단된다", "pip install requests", BLOCK),
    ("pip3_install은_차단된다", "pip3 install requests", BLOCK),
    ("python_dash_m_pip은_차단된다", "python -m pip install requests", BLOCK),
    ("python_manage_py는_차단된다", "python manage.py check", BLOCK),
    ("python3_manage_py는_차단된다", "python3 manage.py migrate", BLOCK),
    ("python_dash_m_pytest는_차단된다", "python -m pytest -q", BLOCK),
    ("체인_명령_속_pytest도_차단된다", "cd tests && pytest -q", BLOCK),
    # 신규: 인터프리터 옵션이 manage.py/-m pytest 앞에 끼는 형태.
    (
        "인터프리터_옵션_u_뒤_manage_py_실행도_차단된다",
        "python3 -u manage.py check",
        BLOCK,
    ),
    (
        "인터프리터_옵션_B_뒤_manage_py_실행도_차단된다",
        "python -B manage.py migrate",
        BLOCK,
    ),
    (
        "인터프리터_옵션_X_dev_뒤_m_pytest_실행도_차단된다",
        "python3 -X dev -m pytest -q",
        BLOCK,
    ),
    # 허용되어야 하는 형태.
    ("uv_run_pytest는_허용된다", "uv run pytest -q", ALLOW),
    ("uv_run_python_manage_py는_허용된다", "uv run python manage.py check", ALLOW),
    (
        "python3_c_한줄_스크립트는_허용된다",
        "python3 -c 'import datetime; print(datetime.date.today())'",
        ALLOW,
    ),
    ("pytest_단어가_인자일_때는_허용된다", "rg pytest tests/core", ALLOW),
    ("pip_단어가_문자열일_때는_허용된다", 'echo "pip install foo"', ALLOW),
    (
        "환경변수_대입_뒤_uv_run_pytest는_허용된다",
        "FOO=bar uv run pytest -q",
        ALLOW,
    ),
]


@pytest.mark.parametrize(
    "command,expected",
    [(command, expected) for _, command, expected in UV_ONLY_CASES],
    ids=[case_id for case_id, _, _ in UV_ONLY_CASES],
)
def test_명령_형태에_따라_uv_only_가드가_허용과_차단을_올바르게_판정한다(
    command, expected, tmp_path
):
    result = _run_hook(UV_ONLY_GUARD, command, tmp_path)

    assert result.returncode == expected


GIT_STAGE_ALL_CASES = [
    # 회귀: 기존에 올바르게 판정되던 형태.
    ("git_add_dash_A는_차단된다", "git add -A", BLOCK),
    ("git_add_dash_dash_all은_차단된다", "git add --all", BLOCK),
    ("git_add_dot은_차단된다", "git add .", BLOCK),
    ("git_add_prompt_plan은_차단된다", "git add prompt_plan.md", BLOCK),
    ("git_commit_dash_a는_차단된다", "git commit -a -m msg", BLOCK),
    ("git_commit_dash_am은_차단된다", "git commit -am msg", BLOCK),
    # 신규: -u/--update 추적 파일 전체 스테이징, 포지셔널 경로로 커밋 끼워넣기,
    # 전역 옵션(-C/-c) 뒤에 숨은 add -A·commit -a.
    ("git_add_dash_u는_차단된다", "git add -u", BLOCK),
    ("git_add_dash_dash_update는_차단된다", "git add --update", BLOCK),
    (
        "git_commit_메시지_뒤_prompt_plan_포지셔널은_차단된다",
        "git commit -m x prompt_plan.md",
        BLOCK,
    ),
    (
        "git_commit_더블대시_뒤_prompt_plan도_차단된다",
        "git commit -m x -- prompt_plan.md",
        BLOCK,
    ),
    ("git_dash_C_옵션_뒤_add_dash_A도_차단된다", "git -C . add -A", BLOCK),
    (
        "git_dash_c_옵션_뒤_commit_dash_a도_차단된다",
        "git -c core.x=y commit -a",
        BLOCK,
    ),
    # 신규: here-string(<<<)을 heredoc(<<) 시작으로 오인해 다음 줄의
    # `git add -A`를 통째로 놓치는 형태(plan-bash-write-guard와 같은 결함).
    (
        "here_string을_heredoc_시작으로_오인해_다음_줄_git_add_dash_A를_놓치지_않는다",
        'cat <<< "hi"\ngit add -A',
        BLOCK,
    ),
    # 허용되어야 하는 형태.
    (
        "git_add_특정_문서_경로는_허용된다",
        "git add docs/plan-archive/track-49.md",
        ALLOW,
    ),
    ("git_commit_메시지만_있으면_허용된다", "git commit -m msg", ALLOW),
    ("git_add_패치_모드는_허용된다", "git add -p", ALLOW),
    ("git_add_dash_A_문자열_언급은_허용된다", 'echo "git add -A"', ALLOW),
    ("git_dash_C_옵션_뒤_status는_허용된다", "git -C . status", ALLOW),
    ("git_add_다른_문서_경로는_허용된다", "git add docs/x.md", ALLOW),
]


@pytest.mark.parametrize(
    "command,expected",
    [(command, expected) for _, command, expected in GIT_STAGE_ALL_CASES],
    ids=[case_id for case_id, _, _ in GIT_STAGE_ALL_CASES],
)
def test_명령_형태에_따라_git_stage_all_가드가_허용과_차단을_올바르게_판정한다(
    command, expected, tmp_path
):
    result = _run_hook(GIT_STAGE_ALL_GUARD, command, tmp_path)

    assert result.returncode == expected


PLAN_BASH_WRITE_CASES = [
    # 회귀: 기존에 올바르게 판정되던 형태.
    ("echo_리다이렉트_덮어쓰기는_차단된다", "echo hi > prompt_plan.md", BLOCK),
    ("echo_리다이렉트_추가도_차단된다", "echo hi >> prompt_plan.md", BLOCK),
    ("tee로_쓰기도_차단된다", "tee prompt_plan.md", BLOCK),
    ("cp_목적지_덮어쓰기는_차단된다", "cp /tmp/a.md prompt_plan.md", BLOCK),
    ("sed_dash_i_직접_수정은_차단된다", "sed -i 's/a/b/' prompt_plan.md", BLOCK),
    ("dd_of_덮어쓰기는_차단된다", "dd of=prompt_plan.md", BLOCK),
    (
        "perl_dash_i_점백업_직접_수정은_차단된다",
        "perl -i.bak -pe 's/a/b/' prompt_plan.md",
        BLOCK,
    ),
    # 신규: rm/unlink/git rm으로 지우는 형태, mv로 원본을 옮겨 없애는 형태,
    # perl의 결합 플래그(-pi), here-string을 heredoc으로 오인하는 형태.
    ("rm으로_지우는_것도_차단된다", "rm prompt_plan.md", BLOCK),
    ("rm_dash_f로_지우는_것도_차단된다", "rm -f prompt_plan.md", BLOCK),
    ("unlink으로_지우는_것도_차단된다", "unlink prompt_plan.md", BLOCK),
    ("git_rm으로_지우는_것도_차단된다", "git rm prompt_plan.md", BLOCK),
    (
        "git_dash_C_옵션_뒤_rm도_차단된다",
        "git -C . rm prompt_plan.md",
        BLOCK,
    ),
    (
        "mv로_원본을_옮겨_없애는_것도_차단된다",
        "mv prompt_plan.md /tmp/x.md",
        BLOCK,
    ),
    (
        "perl_결합_플래그_pi_직접_수정도_차단된다",
        "perl -pi -e 's/a/b/' prompt_plan.md",
        BLOCK,
    ),
    (
        "here_string을_heredoc_시작으로_오인해_다음_줄_쓰기를_놓치지_않는다",
        'cat <<< "hi"\necho x > prompt_plan.md',
        BLOCK,
    ),
    # 허용되어야 하는 형태.
    ("cat으로_읽기만_하면_허용된다", "cat prompt_plan.md", ALLOW),
    ("cp로_읽어서_다른_곳에_쓰면_허용된다", "cp prompt_plan.md /tmp/b.md", ALLOW),
    ("rg로_검색만_하면_허용된다", "rg x prompt_plan.md", ALLOW),
    ("wc로_줄_수만_세면_허용된다", "wc -l prompt_plan.md", ALLOW),
    ("here_string_단독_사용은_허용된다", 'cat <<< "hi"', ALLOW),
    (
        "리다이렉트를_언급하는_문자열은_허용된다",
        'echo "see > prompt_plan.md"',
        ALLOW,
    ),
    ("다른_파일을_지우는_것은_허용된다", "rm /tmp/other.md", ALLOW),
]


@pytest.mark.parametrize(
    "command,expected",
    [(command, expected) for _, command, expected in PLAN_BASH_WRITE_CASES],
    ids=[case_id for case_id, _, _ in PLAN_BASH_WRITE_CASES],
)
def test_명령_형태에_따라_plan_bash_write_가드가_허용과_차단을_올바르게_판정한다(
    command, expected, tmp_path
):
    result = _run_hook(PLAN_BASH_WRITE_GUARD, command, tmp_path)

    assert result.returncode == expected


def _make_dirty_repo(tmp_path):
    """git-destructive-guard는 프로세스 cwd에서 `git status --porcelain`으로
    dirty 여부를 본다. 추적 안 된 파일 1개로 더티 상태를 만들고,
    경로 판정에 쓰이는 prompt_plan.md도 실제 파일로 둔다."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, capture_output=True, text=True)
    (tmp_path / "prompt_plan.md").write_text("plan\n", encoding="utf-8")
    (tmp_path / "untracked.txt").write_text("x\n", encoding="utf-8")


GIT_DESTRUCTIVE_CASES = [
    # 회귀: dirty에서 기존에 올바르게 차단되던 형태.
    ("dirty_git_reset_hard는_차단된다", "git reset --hard", True, BLOCK),
    ("dirty_git_clean_fd는_차단된다", "git clean -fd", True, BLOCK),
    (
        "dirty_git_checkout_더블대시_prompt_plan은_차단된다",
        "git checkout -- prompt_plan.md",
        True,
        BLOCK,
    ),
    ("dirty_git_checkout_dot은_차단된다", "git checkout .", True, BLOCK),
    ("dirty_git_restore_prompt_plan은_차단된다", "git restore prompt_plan.md", True, BLOCK),
    (
        "dirty_git_checkout_HEAD_더블대시_prompt_plan은_차단된다",
        "git checkout HEAD -- prompt_plan.md",
        True,
        BLOCK,
    ),
    # 신규: 더블대시 없이 경로를 가리키는 형태, 전역 옵션(-C/-c) 뒤에 숨은 서브커맨드.
    (
        "dirty_git_checkout_prompt_plan_더블대시_없이도_차단된다",
        "git checkout prompt_plan.md",
        True,
        BLOCK,
    ),
    (
        "dirty_git_checkout_HEAD_prompt_plan_더블대시_없이도_차단된다",
        "git checkout HEAD prompt_plan.md",
        True,
        BLOCK,
    ),
    (
        "dirty_git_dash_C_옵션_뒤_reset_hard도_차단된다",
        "git -C . reset --hard HEAD~1",
        True,
        BLOCK,
    ),
    (
        "dirty_git_dash_C_옵션_뒤_checkout_더블대시도_차단된다",
        "git -C . checkout -- prompt_plan.md",
        True,
        BLOCK,
    ),
    (
        "dirty_git_dash_c_옵션_뒤_clean_fd도_차단된다",
        "git -c x=y clean -fd",
        True,
        BLOCK,
    ),
    # 신규: dry-run 플래그가 있으면 지우지 않으므로 허용되어야 한다.
    ("dirty_git_clean_nd_dry_run은_허용된다", "git clean -nd", True, ALLOW),
    ("dirty_git_clean_n_공백_d_dry_run은_허용된다", "git clean -n -d", True, ALLOW),
    (
        "dirty_git_clean_dash_dash_dry_run_x는_허용된다",
        "git clean --dry-run -x",
        True,
        ALLOW,
    ),
    # 회귀: dirty에서 기존에 올바르게 허용되던 형태(브랜치 전환 등).
    ("dirty_git_checkout_main_브랜치_전환은_허용된다", "git checkout main", True, ALLOW),
    (
        "dirty_git_checkout_슬래시_포함_브랜치_전환은_허용된다",
        "git checkout fix/track-55-review-residuals",
        True,
        ALLOW,
    ),
    ("dirty_git_switch_새_브랜치_생성은_허용된다", "git switch -c x", True, ALLOW),
    ("dirty_git_dash_C_옵션_뒤_status는_허용된다", "git -C . status", True, ALLOW),
    # clean 트리에서는 기존 설계대로 git checkout prompt_plan.md도 허용된다.
    (
        "clean_트리의_git_checkout_prompt_plan은_허용된다",
        "git checkout prompt_plan.md",
        False,
        ALLOW,
    ),
    # 항상 차단: 더티 여부와 무관하게 모든 스태시를 지운다.
    ("dirty_git_stash_clear는_항상_차단된다", "git stash clear", True, BLOCK),
    ("clean_git_stash_clear도_항상_차단된다", "git stash clear", False, BLOCK),
]


@pytest.mark.parametrize(
    "command,dirty,expected",
    [(command, dirty, expected) for _, command, dirty, expected in GIT_DESTRUCTIVE_CASES],
    ids=[case_id for case_id, _, _, _ in GIT_DESTRUCTIVE_CASES],
)
def test_작업트리_상태와_명령_형태에_따라_git_destructive_가드가_허용과_차단을_올바르게_판정한다(
    command, dirty, expected, tmp_path
):
    if dirty:
        _make_dirty_repo(tmp_path)

    result = _run_hook(GIT_DESTRUCTIVE_GUARD, command, tmp_path)

    assert result.returncode == expected
