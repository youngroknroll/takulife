#!/bin/bash
# Python Style Guard - PostToolUse hook (matcher: Edit|Write)
#
# Enforces AGENTS.md "Python Style Guide" (docs/BE/python-conventions.md) right
# after a .py file is edited, using the project's ruff configuration.
#
# Blocks (feedback to the model, file is NOT modified):
#   - `ruff check` violations (imports, relative imports, bugbear, line length)
#   - `ruff format --check` differences
# Allows:
#   - no path, non-.py files, files outside the project root
#   - git-ignored files (e.g. .docs/), files that no longer exist
#   - files excluded by pyproject.toml (migrations/; --force-exclude applies it)
#   - ruff/uv missing or slower than 10 s (warning only)
#
# Known gaps: checks only the edited file, not the rest of the repository;
# Bash-tool writes (sed, heredoc) do not trigger it.
#
# Exit codes: 0 = allow, 2 = feedback to the model (PostToolUse cannot block)

INPUT=$(cat)

python3 - "$INPUT" <<'PY'
import json, os, subprocess, sys

raw = sys.argv[1] if len(sys.argv) > 1 else ""
try:
    data = json.loads(raw)
except Exception:
    sys.exit(0)  # unparsable payload: do not block

path = (data.get("tool_input") or {}).get("file_path") or ""
if not path or not path.endswith(".py"):
    sys.exit(0)

root = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or ""
if not root:
    sys.exit(0)
root = os.path.realpath(root)
target = os.path.realpath(path if os.path.isabs(path) else os.path.join(root, path))
if not target.startswith(root + os.sep) or not os.path.isfile(target):
    sys.exit(0)

try:
    ignored = subprocess.run(
        ["git", "-C", root, "check-ignore", "-q", target], capture_output=True, timeout=10
    ).returncode == 0
except Exception:
    ignored = False
if ignored:
    sys.exit(0)

base = ["uv", "run", "--no-sync", "ruff"]
commands = [
    base + ["check", "--force-exclude", "--no-fix", "--output-format", "concise", target],
    base + ["format", "--check", "--force-exclude", target],
]
output = []
failed = False
for cmd in commands:
    try:
        proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        print("python-style-guard: ruff timed out, skipped", file=sys.stderr)
        sys.exit(0)
    except OSError:
        print("python-style-guard: ruff unavailable, skipped", file=sys.stderr)
        sys.exit(0)
    text = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode in (126, 127) or "Failed to spawn" in text:
        print("python-style-guard: ruff unavailable, skipped", file=sys.stderr)
        sys.exit(0)
    if proc.returncode != 0:
        failed = True
        output.extend(text.splitlines())

if failed:
    print("STYLE VIOLATION (AGENTS.md Python Style Guide / docs/BE/python-conventions.md)",
          file=sys.stderr)
    for line in output[:40]:
        print(line, file=sys.stderr)
    print(f"Fix the file, then re-run: uv run ruff check {path} && "
          f"uv run ruff format --check {path} (format: uv run ruff format {path})",
          file=sys.stderr)
    sys.exit(2)

sys.exit(0)
PY
