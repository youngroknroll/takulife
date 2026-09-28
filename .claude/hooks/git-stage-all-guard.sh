#!/bin/bash
# Git Stage-All Guard - PreToolUse hook (matcher: Bash)
#
# Enforces AGENTS.md "Commit And PR Cadence": stage files explicitly, never
# `git add -A`/`--all`/`.`, and never stage `prompt_plan.md` (it stays
# unstaged so it cannot end up in a commit by accident).
#
# Blocks, regardless of working-tree state:
#   git add -A | git add --all | git add .   (exact token match only —
#     `./archive/`, `.env`, `archive/.gitignore` are unaffected)
#   git add ... prompt_plan.md               (any positional argument)
#   git commit -a | --all | -am | -qa ...    (any flag token combining `a`
#     into a single-dash bundle); the `-m` message argument is never
#     inspected, and `--amend` alone is not a target.
#
# Known gap: string concatenation, nested `bash -c`, and variable-hidden
# arguments defeat this static matching — it is a mistake-prevention guard,
# not a security boundary (AGENTS.md Harness Enforcement).
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
if "git" not in command:
    sys.exit(0)

TARGET = "prompt_plan.md"


def basename(token):
    token = token.strip().strip("'\"")
    return token.rsplit("/", 1)[-1]


def program_tokens(segment):
    try:
        tokens = shlex.split(segment)
    except ValueError:
        tokens = segment.split()
    while tokens and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[0]):
        tokens.pop(0)
    return tokens


STAGE_ALL_TOKENS = {"-A", "--all", "."}
COMMIT_ALL_RE = re.compile(r"-[A-Za-z]*a[A-Za-z]*")


def split_segments(text):
    """Split on ; | & && || \\n, but never inside a quoted string — a naive
    regex split would cut a commit message containing `;` in half."""
    segments = []
    current = []
    quote = None
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if quote:
            current.append(c)
            if c == quote and text[i - 1] != "\\":
                quote = None
            i += 1
            continue
        if c in ("'", '"'):
            quote = c
            current.append(c)
            i += 1
            continue
        if text[i:i + 2] in ("&&", "||"):
            segments.append("".join(current))
            current = []
            i += 2
            continue
        if c in (";", "|", "\n"):
            segments.append("".join(current))
            current = []
            i += 1
            continue
        current.append(c)
        i += 1
    segments.append("".join(current))
    return [s for s in segments if s.strip()]


segments = split_segments(command)

hits = []
for seg in segments:
    tokens = program_tokens(seg)
    if not tokens:
        continue
    prog = tokens[0].rsplit("/", 1)[-1]
    if prog != "git":
        continue
    sub = tokens[1] if len(tokens) > 1 else ""
    rest = tokens[2:]

    if sub == "add":
        if any(t in STAGE_ALL_TOKENS for t in rest):
            hits.append(("git add -A/--all/.", seg.strip()))
        positionals = [t for t in rest if not t.startswith("-")]
        if any(basename(t) == TARGET for t in positionals):
            hits.append(("git add prompt_plan.md", seg.strip()))

    elif sub == "commit":
        for t in rest:
            if t == "--all":
                hits.append(("git commit --all", seg.strip()))
                break
            if t.startswith("-") and not t.startswith("--"):
                if t == "-a" or COMMIT_ALL_RE.fullmatch(t):
                    hits.append(("git commit -a", seg.strip()))
                    break

if hits:
    print("BLOCKED by git stage-all guard (AGENTS.md Commit And PR Cadence)",
          file=sys.stderr)
    for label, seg in hits:
        print(f"  {label} in: {seg[:200]}", file=sys.stderr)
    print("stage files explicitly; prompt_plan.md stays unstaged", file=sys.stderr)
    sys.exit(2)

sys.exit(0)
PY
