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
# Segments are split on `(`, `)`, and backticks (outside quotes) too, so a
# subshell `(git add -A)` or `` `git add -A` `` is still caught.
#
# A heredoc body is only inspected when it is fed to bash/sh/zsh (a shell
# script, so `git add -A` inside it is a real command); one fed to a data
# consumer (`git commit -F -`, `cat`, `tee`) is text, and mentioning
# `git add -A` in a commit message body is not a live command.
#
# Known gap: string concatenation, a git call hidden one layer deeper inside
# `bash -c "git add -A"` (a single quoted token this hook does not parse),
# and variable-hidden arguments defeat this static matching — it is a
# mistake-prevention guard, not a security boundary (AGENTS.md Harness
# Enforcement).
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
    """Split on ; | & && || ( ) ` \\n, but never inside a quoted string — a
    naive regex split would cut a commit message containing `;` in half, and
    a subshell `(cmd)` or `` `cmd` `` would hide `cmd` inside an unmatched
    first token like `(git`."""
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
        if c in (";", "|", "\n", "(", ")", "`"):
            segments.append("".join(current))
            current = []
            i += 1
            continue
        current.append(c)
        i += 1
    segments.append("".join(current))
    return [s for s in segments if s.strip()]


HEREDOC_START = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?")


def extract_heredocs(text):
    """Return (stripped_text, heredocs); see plan-bash-write-guard.sh for the
    identical helper and rationale — the `<<MARKER` line stays, only the
    body and its terminator are removed from the segment scan."""
    lines = text.split("\n")
    n = len(lines)
    skip = set()
    heredocs = []
    i = 0
    while i < n:
        m = HEREDOC_START.search(lines[i])
        if not m:
            i += 1
            continue
        marker = m.group(1)
        consumer_tokens = program_tokens(lines[i][: m.start()])
        consumer_prog = consumer_tokens[0].rsplit("/", 1)[-1] if consumer_tokens else ""
        body_lines = []
        j = i + 1
        while j < n and lines[j].strip() != marker:
            body_lines.append(lines[j])
            skip.add(j)
            j += 1
        if j < n:
            skip.add(j)  # the terminator line itself is not a command
        heredocs.append((lines[i], marker, "\n".join(body_lines), consumer_prog))
        i = j + 1
    stripped_text = "\n".join(l for idx, l in enumerate(lines) if idx not in skip)
    return stripped_text, heredocs


def scan_segments(text, hits):
    for seg in split_segments(text):
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


hits = []

stripped_command, heredocs = extract_heredocs(command)
scan_segments(stripped_command, hits)

for start_line, marker, body, consumer_prog in heredocs:
    if consumer_prog in ("bash", "sh", "zsh"):
        scan_segments(body, hits)
    # else: a data consumer (git, cat, tee, ...) — body is not inspected.

if hits:
    print("BLOCKED by git stage-all guard (AGENTS.md Commit And PR Cadence)",
          file=sys.stderr)
    for label, seg in hits:
        print(f"  {label} in: {seg[:200]}", file=sys.stderr)
    print("stage files explicitly; prompt_plan.md stays unstaged", file=sys.stderr)
    sys.exit(2)

sys.exit(0)
PY
