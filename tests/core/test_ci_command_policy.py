from pathlib import Path
import re


def test_CI_배포_검증이_Python을_실행하면_uv_run을_사용한다():
    workflow_path = Path(__file__).resolve().parents[2] / ".github/workflows/ci.yml"
    deployment_check = workflow_path.read_text().split("- name: Deployment checklist", 1)[1]

    assert "uv run python -c" in deployment_check
    assert "python3 -c" not in deployment_check


def test_운영_문서가_Django_명령을_안내하면_uv_run을_사용한다():
    project_root = Path(__file__).resolve().parents[2]
    runbook_paths = [
        project_root / "docs/deploy-runbook.md",
        project_root / "docs/operations-runbook.md",
    ]

    for runbook_path in runbook_paths:
        bare_commands = re.findall(
            r"(?<!uv run )python manage\.py",
            runbook_path.read_text(),
        )

        assert bare_commands == [], runbook_path
