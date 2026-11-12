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
#   - the same three forms with an interpreter option in front
#     (e.g. `python3 -u manage.py check`, `python3 -X dev -m pytest -q`)
#   - a version-suffixed interpreter (`python3.13 manage.py check`), a
#     relative-path direct execution (`./manage.py check`), or the same
#     forms wrapped in `env [VAR=...] ...` / `time ...`
# Allows:
#   - anything starting with `uv` (including `uv run ./manage.py ...` and
#     `uv run python manage.py ...`)
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
    # 실제 실행 프로그램을 가리는 선두 접두를 전부 건너뛴다: `FOO=bar cmd`의
    # 대입, `env FOO=bar cmd`의 env(그 뒤에 또 대입이 올 수 있어 반복),
    # `time cmd`(인자를 받지 않고 바로 다음 명령을 실행).
    while tokens:
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[0]):
            tokens.pop(0)
        elif tokens[0] in ("env", "time"):
            tokens.pop(0)
        else:
            break
    return tokens

# `-W <arg>`/`-X <opt>` consume the next token; other single-dash flags
# (bare or combined, e.g. `-u`, `-OO`) take none. `-m`/`-c`/`--` end option
# parsing, so `python3 -u manage.py` and `python3 -u -c '...'` both resolve
# to the real program word after skipping only the interpreter options.
VALUE_OPTS = ("-W", "-X")

def skip_interpreter_options(tokens):
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("-m", "-c", "--"):
            break
        if tok in VALUE_OPTS:
            i += 2
            continue
        if re.fullmatch(r"-[A-Za-z]+", tok):
            i += 1
            continue
        break
    return tokens[i:]

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
    elif re.fullmatch(r"python3?(\.\d+)?", prog):
        rest = skip_interpreter_options(rest)
        if rest[:2] == ["-m", "pip"]:
            violations.append((seg.strip(), "`python -m pip`", "uv add / uv remove"))
        elif any(t.endswith("manage.py") for t in rest[:1]):
            violations.append((seg.strip(), "bare `python manage.py`",
                               "uv run python manage.py ..."))
        elif rest[:1] == ["-m"] and rest[1:2] == ["pytest"]:
            violations.append((seg.strip(), "bare `python -m pytest`",
                               "uv run pytest ..."))
    elif prog == "manage.py":
        violations.append((seg.strip(), "direct `manage.py` execution",
                           "uv run python manage.py ..."))

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
