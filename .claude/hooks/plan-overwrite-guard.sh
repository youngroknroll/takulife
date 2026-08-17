#!/bin/bash
# Plan Overwrite Guard - PreToolUse hook (matcher: Write)
#
# Enforces CLAUDE.md: "Never revert unrelated changes or overwrite
# `prompt_plan.md` unless assigned."
#
# `Write` replaces a file wholesale — that is the overwrite the rule names.
# `Edit` changes a named region and is not blocked, so assigned plan updates
# still work. A genuine full rewrite is rare enough to be worth a sentence to
# the user first.
#
# Exit codes: 0 = allow, 2 = block (stderr is fed back to the model)

INPUT=$(cat)

python3 - "$INPUT" <<'PY'
import json, os, sys

raw = sys.argv[1] if len(sys.argv) > 1 else ""
try:
    data = json.loads(raw)
except Exception:
    sys.exit(0)  # unparsable payload: do not block

path = (data.get("tool_input") or {}).get("file_path") or ""
if not path:
    sys.exit(0)

PROTECTED = {"prompt_plan.md"}

if os.path.basename(path) in PROTECTED:
    print("BLOCKED by plan overwrite guard (CLAUDE.md)", file=sys.stderr)
    print(f"  Write would replace all of: {path}", file=sys.stderr)
    print("  `prompt_plan.md` is not overwritten unless the task assigns it.",
          file=sys.stderr)
    print("  Use Edit for a targeted change, or confirm the full rewrite with "
          "the user first.", file=sys.stderr)
    sys.exit(2)

sys.exit(0)
PY
