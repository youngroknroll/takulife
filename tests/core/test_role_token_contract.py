from pathlib import Path
import re

import pytest

pytestmark = pytest.mark.contract

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CSS_ROOT = PROJECT_ROOT / "static/css"

# 여러 화면이 함께 움직여야 하는 값만 싣는다. 새 역할 토큰은 여기에 추가한다.
ROLE_TOKEN_DEFINITION_FILES = {
    "--page-pad-x": "static/css/tokens.css",
    "--site-header-h": "static/css/components/site-chrome.css",
    "--site-tabbar-h": "static/css/components/site-chrome.css",
}

_COMMENT = re.compile(r"/\*.*?\*/", re.DOTALL)


def _source_css_files():
    """dist(빌드 산출물)를 뺀 소스 CSS를 정렬해 돌려준다."""
    return sorted(
        path for path in CSS_ROOT.rglob("*.css") if "dist" not in path.relative_to(CSS_ROOT).parts
    )


def _defining_files(token):
    """주석을 뺀 소스에서 `--토큰:` 선언이 있는 파일의 상대 경로 목록."""
    declaration = re.compile(rf"(?<![\w-]){re.escape(token)}\s*:")
    defining = []
    for path in _source_css_files():
        text = _COMMENT.sub("", path.read_text(encoding="utf-8"))
        if declaration.search(text):
            defining.append(path.relative_to(PROJECT_ROOT).as_posix())
    return defining


def test_역할_토큰은_레지스트리가_적은_파일에서만_정의된다():
    """계약 가드: 역할 토큰은 레지스트리가 적은 파일 한 곳에서만 선언된다.

    한 파일만 고치면 모든 화면이 따라오게 하려는 가드다. 다른 CSS가
    같은 토큰을 다시 선언하면 화면마다 값이 갈라진다.

    소스에서 정의 위치만 본다. 화면 여백을 재는 테스트가 아니다.
    잡지 못하는 것: 정의 파일 안에서 :root 밖 선택자로 다시 정의하기,
    토큰 없이 숫자를 직접 쓰는 새 규칙, 토큰을 쓰던 곳을 다른 화면
    폭에서 숫자로 덮어쓰기, 화면에 실제로 그려지는 여백 값.

    뮤테이션 지점: 페이지 CSS에 --page-pad-x 선언을 넣으면 Red가 된다.
    """
    mismatches = []
    for token, expected_file in ROLE_TOKEN_DEFINITION_FILES.items():
        actual_files = _defining_files(token)
        if actual_files != [expected_file]:
            mismatches.append(f"{token}: 기대 정의 파일 {expected_file}, 실제 {actual_files}")

    assert not mismatches, "역할 토큰 정의 위치가 레지스트리와 다르다:\n" + "\n".join(mismatches)
