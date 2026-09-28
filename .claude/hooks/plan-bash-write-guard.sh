#!/bin/bash
# Plan Bash Write Guard - PreToolUse hook (matcher: Bash)
#
# Enforces AGENTS.md "prompt_plan.md is edited with the Edit tool only" by
# catching Bash-side write paths that bypass the plan-overwrite-guard (which
# only sees the Write tool) and the plan-number-tag-guard (which only sees
# Edit/Write). Track 40 recorded one real bypass via a Python heredoc.
#
# Blocks a command whose target is `prompt_plan.md` via:
#   - shell redirection: >, >>, 1>, 1>>, 2>, 2>>, &> (target token only,
#     not a source argument earlier in the same command)
#   - `tee` with `prompt_plan.md` as any positional (non-flag) argument
#   - `cp`/`mv` with `prompt_plan.md` as the last positional argument
#     (skipped when `-t`/`--target-directory` names another destination)
#   - `sed -i`/`perl -i`/`awk -i inplace` naming `prompt_plan.md`
#   - `python`/`python3`/`uv ... -c "<code>"` whose code string mentions
#     `prompt_plan.md` together with a write pattern (`write_text(`,
#     `.write(`, or `open(..., "w"/"a")`)
#   - a heredoc (`<<MARKER`) fed to python/python3/uv/perl whose body has
#     the same target-plus-write-pattern combination
#
# Read-only uses (`cat`, `sed -n`, `rg`, `wc`, `git diff ... > /tmp/x`,
# `echo "prompt_plan.md"`) are not touched.
#
# Known gap: string concatenation, nested `bash -c`, and variable-hidden
# filenames defeat this static matching — it is a mistake-prevention guard,
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
if not command.strip():
    sys.exit(0)

TARGET = "prompt_plan.md"


def basename(token):
    token = token.strip().strip("'\"")
    return token.rsplit("/", 1)[-1]


def is_target(token):
    return basename(token) == TARGET


def program_tokens(segment):
    try:
        tokens = shlex.split(segment)
    except ValueError:
        tokens = segment.split()
    while tokens and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[0]):
        tokens.pop(0)
    return tokens


def program_name(tokens):
    return tokens[0].rsplit("/", 1)[-1] if tokens else ""


WRITE_PATTERN = re.compile(
    r"write_text\s*\(|\.write\s*\(|open\([^)]*[\"'](?:w|a)[\"']"
)


def has_write_pattern(code):
    return bool(WRITE_PATTERN.search(code))


REDIRECT_RE = re.compile(r"(&>|[12]?>>|[12]?>)\s*(\S+)")


def split_segments(text):
    """Split on ; | & && || \\n, but never inside a quoted string — a naive
    regex split would cut a `python -c "a; b"` payload at the semicolon."""
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


hits = []

segments = split_segments(command)

for seg in segments:
    # (a) redirection: only the token right after the operator is the target.
    for m in REDIRECT_RE.finditer(seg):
        if is_target(m.group(2)):
            hits.append(("redirect", seg.strip()))

    tokens = program_tokens(seg)
    if not tokens:
        continue
    prog = program_name(tokens)

    # (b) tee: any positional (non-flag) argument.
    if prog == "tee":
        for t in tokens[1:]:
            if not t.startswith("-") and is_target(t):
                hits.append(("tee", seg.strip()))

    # (c) cp/mv: last positional argument, unless retargeted with -t/--target-directory.
    elif prog in ("cp", "mv"):
        has_target_flag = any(
            t == "-t" or t.startswith("--target-directory") for t in tokens[1:]
        )
        if not has_target_flag:
            positionals = [t for t in tokens[1:] if not t.startswith("-")]
            if positionals and is_target(positionals[-1]):
                hits.append((f"{prog} last arg", seg.strip()))

    # (d) sed/perl/awk in-place edit naming the target.
    if prog == "sed":
        if any(t == "-i" or t.startswith("-i.") or t == "--in-place" for t in tokens[1:]):
            positionals = [t for t in tokens[1:] if not t.startswith("-")]
            if any(is_target(t) for t in positionals):
                hits.append(("sed -i", seg.strip()))
    elif prog == "perl":
        if any(t == "-i" or t.startswith("-i.") for t in tokens[1:]):
            positionals = [t for t in tokens[1:] if not t.startswith("-")]
            if any(is_target(t) for t in positionals):
                hits.append(("perl -i", seg.strip()))
    elif prog == "awk":
        rest = tokens[1:]
        if "-i" in rest and "inplace" in rest:
            positionals = [t for t in rest if not t.startswith("-") and t != "inplace"]
            if any(is_target(t) for t in positionals):
                hits.append(("awk -i inplace", seg.strip()))

    # (e) python/python3/uv -c "<code>" combining the target with a write call.
    if prog in ("python", "python3", "uv") and "-c" in tokens:
        idx = tokens.index("-c")
        if idx + 1 < len(tokens):
            code = tokens[idx + 1]
            if TARGET in code and has_write_pattern(code):
                hits.append(("python -c write", seg.strip()))

# Heredoc bodies fed to an interpreter: extracted by line, not by segment,
# since the body itself contains the newlines the segment split uses.
HEREDOC_START = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?")
lines = command.split("\n")
for i, line in enumerate(lines):
    m = HEREDOC_START.search(line)
    if not m:
        continue
    marker = m.group(1)
    tokens = program_tokens(line[: m.start()])
    prog = program_name(tokens)
    if prog not in ("python", "python3", "uv", "perl"):
        continue
    body_lines = []
    for j in range(i + 1, len(lines)):
        if lines[j].strip() == marker:
            break
        body_lines.append(lines[j])
    body = "\n".join(body_lines)
    if TARGET in body and has_write_pattern(body):
        hits.append(("heredoc write", line.strip()))

if hits:
    print("BLOCKED by plan bash write guard (AGENTS.md Harness Enforcement)",
          file=sys.stderr)
    for label, seg in hits:
        print(f"  {label} in: {seg[:200]}", file=sys.stderr)
    print("Edit prompt_plan.md with the Edit tool only.", file=sys.stderr)
    sys.exit(2)

sys.exit(0)
PY
