"""컨테이너 기동 명령 계약.

`docker/entrypoint.sh`의 gunicorn 기동 명령은 텍스트로만 확인할 수 있다.
워커 타임아웃 플래그가 조용히 사라지는 회귀를 막는다.
"""
import re
from pathlib import Path

import pytest


pytestmark = pytest.mark.contract

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# docs/deploy-runbook.md §1 env 표와 같은 값이다.
DOCUMENTED_GUNICORN_TIMEOUT_SECONDS = 120


def _logical_lines(text):
    lines = []
    pending = ""
    for raw in text.splitlines():
        stripped = raw.strip()
        if not pending and stripped.startswith("#"):
            continue
        if stripped.endswith("\\"):
            pending += stripped[:-1].rstrip() + " "
            continue
        lines.append((pending + stripped).strip())
        pending = ""
    if pending:
        lines.append(pending.strip())
    return lines


def test_컨테이너_기동_명령은_GUNICORN_TIMEOUT_환경변수와_문서화된_기본_타임아웃으로_워커_타임아웃을_정한다():
    """gunicorn 기동 명령이 `--timeout ${GUNICORN_TIMEOUT:-120}` 형태를 유지해야 한다.

    셸 스크립트라 실행 대신 텍스트로 확인하며, 플래그가 조용히 사라지는 회귀를 막는다.
    """
    text = (PROJECT_ROOT / "docker" / "entrypoint.sh").read_text(encoding="utf-8")

    gunicorn_lines = [
        line for line in _logical_lines(text) if line.startswith("exec gunicorn")
    ]
    assert len(gunicorn_lines) == 1

    match = re.search(
        r'--timeout\s+"?\$\{GUNICORN_TIMEOUT:-(\d+)\}"?', gunicorn_lines[0]
    )
    assert match is not None
    assert int(match.group(1)) == DOCUMENTED_GUNICORN_TIMEOUT_SECONDS
