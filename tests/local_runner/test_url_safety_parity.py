"""서버 URL 안전 판정(drafts/url_safety.py)과 러너 복제본
(local_runner/url_safety.py)이 실행 로직에서 갈라지지 않았는지 지키는
회귀 가드다. 한쪽만 고치면 어느 한쪽에만 구멍이 생긴다. drafts 모듈은
임포트하지 않고 파일 텍스트만 읽는다 — local_runner 패키지의 서버 도메인
임포트 금지 계약이 테스트 자체에는 걸리지 않지만, 읽기로 처리하는 편이
의도가 분명하다."""
import pathlib

import pytest


pytestmark = pytest.mark.contract

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
_SERVER_PATH = _REPO_ROOT / "drafts" / "url_safety.py"
_RUNNER_PATH = _REPO_ROOT / "local_runner" / "url_safety.py"


def _normalize(text):
    """주석 줄, 여러 줄 docstring, 빈 줄을 제거해 실행 로직 줄만 남긴다."""
    lines = []
    in_docstring = False
    docstring_delim = None
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if in_docstring:
            if docstring_delim in stripped:
                in_docstring = False
            continue
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        if stripped.startswith('"""') or stripped.startswith("'''"):
            delim = stripped[:3]
            if delim in stripped[3:]:
                continue  # 한 줄짜리 docstring은 통째로 건너뛴다.
            in_docstring = True
            docstring_delim = delim
            continue
        lines.append(stripped)
    return lines


def test_서버와_러너의_URL_안전_판정_로직이_문자_그대로_일치한다():
    server_lines = _normalize(_SERVER_PATH.read_text(encoding="utf-8"))
    runner_lines = _normalize(_RUNNER_PATH.read_text(encoding="utf-8"))

    for index, (server_line, runner_line) in enumerate(zip(server_lines, runner_lines)):
        assert server_line == runner_line, (
            f"{index}번째 실행 로직 줄이 다르다: "
            f"서버={server_line!r} / 러너={runner_line!r}"
        )

    assert len(server_lines) == len(runner_lines), (
        f"실행 로직 줄 수가 다르다: 서버={len(server_lines)}줄, 러너={len(runner_lines)}줄"
    )
