"""launchd 러너 래퍼(`local_runner/launchd/run-runner.sh`)의 PATH 계약.

래퍼가 claude 가드를 env 파일 소싱보다 먼저 평가하면 `TAKULIFE_RUNNER_PATH_PREPEND`가
적용되기 전에 "찾지 못해" 메시지로 조용히 종료 코드 0이 되어 러너가 영구히 뜨지 않는다.
래퍼는 BSD·GNU stat 둘 다 지원해 이 테스트가 Linux CI에서도 실행된다.
"""

from pathlib import Path
import subprocess

import pytest

pytestmark = pytest.mark.contract

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RUNNER_WRAPPER_PATH = PROJECT_ROOT / "local_runner/launchd/run-runner.sh"


def test_환경파일의_PATH_PREPEND_디렉터리에_있는_claude_스텁을_래퍼가_찾는다(tmp_path):
    # Given: 가짜 HOME, env 파일(600), PREPEND 디렉터리의 claude·uv 스텁.
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    stub_dir = tmp_path / "stub-bin"
    stub_dir.mkdir()

    claude_stub = stub_dir / "claude"
    claude_stub.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    claude_stub.chmod(0o755)

    uv_stub = stub_dir / "uv"
    uv_stub.write_text("#!/bin/sh\necho stub-uv-started\n", encoding="utf-8")
    uv_stub.chmod(0o755)

    env_file = fake_home / ".takulife-runner.env"
    env_file.write_text(f"TAKULIFE_RUNNER_PATH_PREPEND={stub_dir}\n", encoding="utf-8")
    env_file.chmod(0o600)

    # When: 래퍼를 최소 PATH로 실행한다(PREPEND 디렉터리는 PATH에 없음).
    result = subprocess.run(
        ["/bin/sh", str(RUNNER_WRAPPER_PATH)],
        env={"HOME": str(fake_home), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        timeout=30,
    )

    # Then: PREPEND 경로의 claude·uv 가드를 통과해 exec까지 간다.
    assert "stub-uv-started" in result.stdout
    assert "claude 실행 파일을 PATH에서 찾지 못해" not in result.stdout
    assert result.returncode == 0
