import ast
from pathlib import Path

import pytest

from tests.core.test_architecture_boundaries import PROJECT_ROOT, _domain_source_files


pytestmark = pytest.mark.contract

# superuser 승격/해제는 shell(createsuperuser, 커스텀 관리 명령)로만 한다는
# 2026-09-07 사용자 결정(docs/BE/staff-account-operations.md (b))을 고정한다.
# 콘솔·서비스·웹 어디에서도 is_superuser를 대입하면 안 된다.
SCANNED_APPS = ["staff", "accounts", "web", "core", "events", "drafts", "archive", "config"]

# 유일한 합법 경로 두 곳은 스캔에서 뺀다 — shell(createsuperuser) 경로 그 자체다.
SHELL_ONLY_EXCLUSIONS = {Path("accounts/managers.py")}
SHELL_ONLY_EXCLUDED_DIR_PARTS = ("accounts", "management")

# 읽기 필터 호출은 is_superuser= 키워드를 써도 위반이 아니다.
ALLOWED_READ_CALL_NAMES = {"filter", "exclude", "get", "Q", "only", "values", "values_list", "annotate"}


def _is_shell_only_path(rel_path):
    if rel_path in SHELL_ONLY_EXCLUSIONS:
        return True
    return rel_path.parts[: len(SHELL_ONLY_EXCLUDED_DIR_PARTS)] == SHELL_ONLY_EXCLUDED_DIR_PARTS


def _scannable_paths(root, app_names):
    return [
        path
        for path in _domain_source_files(root, app_names)
        if not _is_shell_only_path(path.relative_to(root))
    ]


def _call_func_name(call_node):
    if isinstance(call_node.func, ast.Attribute):
        return call_node.func.attr
    if isinstance(call_node.func, ast.Name):
        return call_node.func.id
    return None


def _superuser_write_sites(paths):
    """paths 각각을 AST로 훑어 is_superuser를 '바꾸는' 지점만 "파일:줄" 문자열로
    모은다. 대입(Store)·setdefault/update의 첫 인자 문자열·읽기 필터가 아닌
    호출의 키워드 인자가 대상이고, 단순 읽기(Load, filter/exclude/get/Q 등)는
    뺀다."""
    sites = []
    for path in paths:
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and node.attr == "is_superuser"
                and isinstance(node.ctx, ast.Store)
            ):
                sites.append(f"{path}:{node.lineno}")
                continue

            if not isinstance(node, ast.Call):
                continue

            func_name = _call_func_name(node)

            if func_name in {"setdefault", "update"} and node.args:
                first_arg = node.args[0]
                if isinstance(first_arg, ast.Constant) and first_arg.value == "is_superuser":
                    sites.append(f"{path}:{node.lineno}")
                    continue

            if func_name in ALLOWED_READ_CALL_NAMES:
                continue

            for keyword in node.keywords:
                if keyword.arg == "is_superuser":
                    sites.append(f"{path}:{node.lineno}")
                    break

    return sites


def test_앱_소스에는_is_superuser를_바꾸는_경로가_없다():
    """superuser는 shell로만 만들고 바꾼다는 사용자 결정을 실제 저장소에
    고정한다 — 유일한 합법 대입은 accounts/managers.py와
    accounts/management/ 아래(둘 다 스캔 제외)뿐이어야 한다."""
    scannable = _scannable_paths(PROJECT_ROOT, SCANNED_APPS)

    violations = _superuser_write_sites(scannable)

    assert not violations, violations


def test_대입_위반이_있는_파일은_가드가_잡는다(tmp_path):
    (tmp_path / "staff").mkdir()
    (tmp_path / "staff" / "leak.py").write_text(
        "def promote(user, extra):\n"
        "    user.is_superuser = True\n"
        "    User.objects.create(is_superuser=True)\n"
        '    extra.setdefault("is_superuser", True)\n'
    )

    violations = _superuser_write_sites(_scannable_paths(tmp_path, ["staff"]))

    assert len(violations) == 3, violations


def test_읽기_전용_사용은_위반이_아니다(tmp_path):
    (tmp_path / "staff").mkdir()
    (tmp_path / "staff" / "readonly.py").write_text(
        "def describe(user, qs):\n"
        "    if user.is_superuser:\n"
        "        pass\n"
        "    qs.filter(is_superuser=True)\n"
        '    qs.values("is_superuser")\n'
    )

    violations = _superuser_write_sites(_scannable_paths(tmp_path, ["staff"]))

    assert violations == []
