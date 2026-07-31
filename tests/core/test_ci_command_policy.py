from pathlib import Path
import re


def test_CI_배포_검증이_Python을_실행하면_uv_run을_사용한다():
    workflow_path = Path(__file__).resolve().parents[2] / ".github/workflows/ci.yml"
    deployment_check = workflow_path.read_text().split("- name: Deployment checklist", 1)[1]

    assert "uv run python -c" in deployment_check
    assert "python3 -c" not in deployment_check


def test_운영_문서가_Django_명령을_안내하면_예외_표식_없는_한_uv_run을_사용한다():
    # 런타임 이미지엔 uv가 없어(Dockerfile:3-4) 컨테이너 안 명령엔 uv run을 쓰면 깨진다.
    # `<!-- uv-run-exempt: ... -->` 표식이 명령 앞(80자 이내)에 있을 때만 예외를 허용한다.
    project_root = Path(__file__).resolve().parents[2]
    runbook_paths = [
        project_root / "docs/deploy-runbook.md",
        project_root / "docs/operations-runbook.md",
    ]
    EXEMPT_MARKER_PATTERN = re.compile(r"<!--\s*uv-run-exempt:[^>]*-->")
    MAX_MARKER_DISTANCE = 80

    for runbook_path in runbook_paths:
        text = runbook_path.read_text()
        marker_ends = [m.end() for m in EXEMPT_MARKER_PATTERN.finditer(text)]

        unmarked_bare_commands = [
            match.start()
            for match in re.finditer(r"(?<!uv run )python manage\.py", text)
            if not any(
                0 <= match.start() - marker_end <= MAX_MARKER_DISTANCE
                for marker_end in marker_ends
            )
        ]

        assert unmarked_bare_commands == [], runbook_path
