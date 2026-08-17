#!/bin/bash
# uv-only Guard - PreToolUse hook (matcher: Bash)
#
# Enforces AGENTS.md "Package And Command Policy (uv-only)" deterministically
# instead of relying on the model reading the rule.
#
# Blocks:
#   - bare `pytest ...`            -> must be `uv run pytest ...`
#   - `python|python3 manage.py`   -> must be `uv run python manage.py ...`
#   - `pip install`, `python -m pip`, `pip3 ...`
# Allows:
#   - anything starting with `uv`
#   - `python3 -c '...'` one-liners (date/JSON utilities, not project runtime)
#   - commands where the python/pytest word is an argument, not the program
#
# Exit codes: 0 = allow, 2 = block (stderr is fed back to the model)

INPUT=$(cat)

python3 - "$INPUT" <<'PY'
import json, re, shlex, sys

raw = sys.argv[1] if len(sys.argv) > 1 else ""
try:
    data = json.loads(raw)
except Exception:
    sys.exit(0)  # unparsable payload: do not block

command = (data.get("tool_input") or {}).get("command") or ""
if not command.strip():
    sys.exit(0)

# Split into pipeline/list segments so `cd x && pytest` is inspected too.
segments = [s for s in re.split(r"\|\||&&|[;|\n]", command) if s.strip()]

def first_tokens(segment):
    try:
        tokens = shlex.split(segment)
    except ValueError:
        tokens = segment.split()
    # skip leading env assignments like FOO=bar cmd
    while tokens and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[0]):
        tokens.pop(0)
    return tokens

violations = []
for seg in segments:
    tokens = first_tokens(seg)
    if not tokens:
        continue
    prog = tokens[0].rsplit("/", 1)[-1]
    rest = tokens[1:]

    if prog == "uv":
        continue

    if prog == "pytest":
        violations.append((seg.strip(), "bare `pytest`", "uv run pytest ..."))
    elif prog in ("pip", "pip3"):
        violations.append((seg.strip(), f"`{prog}`", "uv add / uv remove"))
    elif prog in ("python", "python3"):
        if rest[:2] == ["-m", "pip"]:
            violations.append((seg.strip(), "`python -m pip`", "uv add / uv remove"))
        elif any(t.endswith("manage.py") for t in rest[:1]):
            violations.append((seg.strip(), "bare `python manage.py`",
                               "uv run python manage.py ..."))
        elif rest[:1] == ["-m"] and rest[1:2] == ["pytest"]:
            violations.append((seg.strip(), "bare `python -m pytest`",
                               "uv run pytest ..."))

if violations:
    print("BLOCKED by uv-only guard (AGENTS.md: Package And Command Policy)",
          file=sys.stderr)
    for seg, what, fix in violations:
        print(f"  {what} in: {seg[:160]}", file=sys.stderr)
        print(f"  use instead: {fix}", file=sys.stderr)
    print("Bare interpreters resolve to anaconda, not the project venv.",
          file=sys.stderr)
    sys.exit(2)

sys.exit(0)
PY
