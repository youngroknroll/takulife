"""가드: tests/ 트리 소스에 비밀번호류 리터럴·자격증명 URI 리터럴이 남지 않게 한다.

GitGuardian이 실제로 잡는 두 형태를 소스 리터럴로 남기지 말고 `valid_password`
(secrets 런타임 조립, tests/conftest.py) 관례를 쓰라는 저장소 규약을 조언
산문이 아니라 가드로 강제한다. ①이름에 "password"가 포함된 kwarg/할당
(대소문자 무시, `db_password`류 포함)에 4자 이상 문자열 상수(단, "/"로
시작하는 URL 경로 값은 예외) ②`스킴://사용자:비밀번호@호스트` 형태의 URI
상수. 패턴①의 이름·길이·경로 예외는 PR #316에서 실측한 GitGuardian Generic
Password 탐지 지형(이름 포함이면 4자도 잡되 경로 상수는 미탐지)을 그대로
따른다.

GitGuardian은 AST가 아니라 원시 텍스트를 스캔하므로, 이 파일 자신의 캐너리·
단위 픽스처 문자열도 소스에 `password…='값'` 연속 패턴이나 완전한
`스킴://u:p@h` URI를 그대로 남기면 이 가드 파일 자체가 재탐지된다(PR #316
실측). 그래서 모든 픽스처 문자열은 조각 결합(`.format` + 문자열 덧셈)으로
런타임에만 조립한다 — 기록되는 픽스처 파일 내용 자체는 이전과 동일하므로
검출력은 그대로다.
"""
import ast
import re
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MIN_PASSWORD_LITERAL_LENGTH = 4
CREDENTIAL_URI_RE = re.compile(r"^\w+://[^/\s:@]+:[^/\s@]+@")

# 조각 결합으로만 조립한다 — 상수 이름 자체에도 "password"를 넣지 않는다.
# GitGuardian은 이름에 "password"가 포함된 할당을 원시 텍스트로 잡으므로
# (PR #316 실측), 값뿐 아니라 대입 대상 이름도 그 단어를 피해야 한다.
_KWARG_NAME_FRAGMENT = "pass" + "word"


def _name_contains_password(name):
    return "password" in name.lower()


def _is_password_literal_value(node):
    return (
        isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and len(node.value) >= MIN_PASSWORD_LITERAL_LENGTH
        and not node.value.startswith("/")
    )


def _assign_targets_password(targets):
    for target in targets:
        if isinstance(target, ast.Name) and _name_contains_password(target.id):
            return True
        if isinstance(target, ast.Attribute) and _name_contains_password(target.attr):
            return True
    return False


def _password_literal_violations(path):
    """이름에 "password"가 포함된 kwarg/할당에 4자 이상 문자열 상수(경로 값 제외)가
    오면 (행, 사유)를 모은다."""
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        return []

    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            for keyword in node.keywords:
                if (
                    keyword.arg
                    and _name_contains_password(keyword.arg)
                    and _is_password_literal_value(keyword.value)
                ):
                    violations.append((keyword.value.lineno, "password류 kwarg 리터럴"))
        elif isinstance(node, ast.Assign):
            if _assign_targets_password(node.targets) and _is_password_literal_value(node.value):
                violations.append((node.lineno, "password류 할당 리터럴"))
    return violations


def _credential_uri_violations(path):
    """`스킴://사용자:비밀번호@호스트` 형태와 매치되는 문자열 상수를 (행, 사유)로 모은다.

    f-string(JoinedStr)은 ast.Constant가 아니라 이 스캔 밖이다 — 런타임
    조립으로 자격증명 URI를 만드는 저장소 관례를 그대로 허용하는 근거다.
    """
    try:
        tree = ast.parse(path.read_text())
    except SyntaxError:
        return []

    violations = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and CREDENTIAL_URI_RE.search(node.value)
        ):
            violations.append((node.lineno, "자격증명 URI 리터럴"))
    return violations


def _file_violations(path):
    return _password_literal_violations(path) + _credential_uri_violations(path)


def _iter_tracked_test_files(root):
    """`git ls-files`로 추적 파일 중 tests/ 아래 *.py만 추린다 — 스캔 대상 0건이면 조용히 통과하지 않는다."""
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    )
    tracked_paths = [line for line in result.stdout.splitlines() if line]
    files = [
        root / rel_path
        for rel_path in tracked_paths
        if rel_path.startswith("tests/")
        and rel_path.endswith(".py")
        and (root / rel_path).is_file()
    ]
    assert files, "git ls-files로 얻은 tests/ 스캔 대상이 0개다 — 가드가 죽은 채로 통과하면 안 된다"
    return sorted(files)


def test_password_kwarg에_4자_이상_상수가_있으면_위반이다(tmp_path):
    fixture = tmp_path / "fixture.py"
    fixture.write_text(
        "create_user(email='a@example.com', {kw}='abcd')\n".format(
            kw=_KWARG_NAME_FRAGMENT
        )
    )

    assert _password_literal_violations(fixture)


def test_password_kwarg가_3자면_경계값으로_통과한다(tmp_path):
    fixture = tmp_path / "fixture.py"
    fixture.write_text(
        "create_user(email='a@example.com', {kw}='abc')\n".format(
            kw=_KWARG_NAME_FRAGMENT
        )
    )

    assert not _password_literal_violations(fixture)


def test_password_할당에_4자_이상_상수가_있으면_위반이다(tmp_path):
    fixture = tmp_path / "fixture.py"
    fixture.write_text("{kw} = 'abcd'\n".format(kw=_KWARG_NAME_FRAGMENT))

    assert _password_literal_violations(fixture)


def test_password_할당값이_변수_참조면_위반이_아니다(tmp_path):
    fixture = tmp_path / "fixture.py"
    fixture.write_text(
        "{kw} = some_generated_value\n".format(kw=_KWARG_NAME_FRAGMENT)
    )

    assert not _password_literal_violations(fixture)


def test_이름에_password가_포함된_db_password류_할당도_위반이다(tmp_path):
    fixture = tmp_path / "fixture.py"
    fixture.write_text(
        "db_{kw} = 'abcd'\n".format(kw=_KWARG_NAME_FRAGMENT)
    )

    assert _password_literal_violations(fixture)


def test_이름에_password가_포함돼도_값이_url_경로면_위반이_아니다(tmp_path):
    fixture = tmp_path / "fixture.py"
    fixture.write_text(
        "{kw}_CHANGE_URL = '/accounts/{kw}/change/'\n".format(
            kw=_KWARG_NAME_FRAGMENT
        )
    )

    assert not _password_literal_violations(fixture)


def test_자격증명이_포함된_uri_상수는_위반이다(tmp_path):
    fixture = tmp_path / "fixture.py"
    fixture.write_text(
        "DATABASE_URL = 'postgresql://{cred}@localhost:5432/taku'\n".format(
            cred="taku:" + "taku"
        )
    )

    assert _credential_uri_violations(fixture)


def test_자격증명이_없는_uri_상수는_위반이_아니다(tmp_path):
    fixture = tmp_path / "fixture.py"
    fixture.write_text('OFFICIAL_URL = "https://example.com/about"\n')

    assert not _credential_uri_violations(fixture)


def test_두_판정_함수가_합성_캐너리_파일에서_각각_실제로_위반을_검출한다(tmp_path):
    """판정 함수가 죽어서 항상 빈 목록을 돌려주는 사고를 막는 양성 대조 —
    패턴①·②를 한 파일에 함께 심어 둘 다 잡히는지 확인한다."""
    fixture = tmp_path / "canary.py"
    fixture.write_text(
        "create_user(email='a@example.com', {kw}='abcd')\n".format(
            kw=_KWARG_NAME_FRAGMENT
        )
        + "DATABASE_URL = 'postgresql://{cred}@localhost:5432/taku'\n".format(
            cred="taku:" + "taku"
        )
    )

    assert _password_literal_violations(fixture)
    assert _credential_uri_violations(fixture)


def test_tests_트리_전수_스윕에_비밀번호_자격증명_uri_리터럴이_없다():
    violations = []
    for path in _iter_tracked_test_files(PROJECT_ROOT):
        rel_path = path.relative_to(PROJECT_ROOT)
        for lineno, reason in _file_violations(path):
            violations.append(f"{rel_path}:{lineno}: {reason}")

    assert not violations, "\n".join(violations)
