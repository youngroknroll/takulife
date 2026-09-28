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
#     the same target-plus-write-pattern combination; a heredoc fed to
#     bash/sh/zsh whose body (a shell script) trips any of the rules above.
#     A heredoc body is only inspected when it is being interpreted as code —
#     one fed to a data consumer (`git commit -F -`, `cat > file`, `tee`) is
#     text, and mentioning `prompt_plan.md` or `>` in it is not a live write.
#   - `dd of=prompt_plan.md` (an `if=prompt_plan.md` source is a read, not
#     blocked); `install` with `prompt_plan.md` as the last positional
#     argument (skipped when `-t`/`--target-directory` names another
#     destination, same as `cp`/`mv`)
#
# Read-only uses (`cat`, `sed -n`, `rg`, `wc`, `git diff ... > /tmp/x`,
# `echo "prompt_plan.md"`, and a quoted string that merely mentions a
# redirect, e.g. `echo "see > prompt_plan.md for details"`) are not touched.
#
# Segments are split on `(`, `)`, and backticks (outside quotes) too, so a
# subshell `(echo x > prompt_plan.md)` or a command substitution
# `` `echo x > prompt_plan.md` `` is still caught, and the redirect check
# runs on shlex tokens (not raw segment text) so a quoted string can never
# be mistaken for a live redirect target.
#
# Known gap: string concatenation, a write hidden one layer deeper inside
# `bash -c "..."` (a single quoted token this hook does not parse), and
# variable-hidden filenames defeat this static matching — it is a
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


# Longest operator first so a startswith() scan never matches a short prefix
# of a longer one (">" must not steal the match meant for ">>").
REDIRECT_OPS = ("2>>", "1>>", "&>", ">>", "2>", "1>", ">")


def redirect_targets(tokens):
    """Targets named by a redirection operator, found in already-tokenized
    (shlex) form so a quoted string like "see > prompt_plan.md" stays one
    token and is never mistaken for `> prompt_plan.md`."""
    targets = []
    for i, tok in enumerate(tokens):
        for op in REDIRECT_OPS:
            if tok == op:
                if i + 1 < len(tokens):
                    targets.append(tokens[i + 1])
                break
            if tok.startswith(op) and len(tok) > len(op):
                targets.append(tok[len(op):])
                break
    return targets


def split_segments(text):
    """Split on ; | & && || ( ) ` \\n, but never inside a quoted string — a
    naive regex split would cut a `python -c "a; b"` payload at the
    semicolon, and a subshell `(cmd)` or `` `cmd` `` would hide `cmd` inside
    an unmatched first token like `(git`."""
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


def scan_segments(text, hits):
    """Apply every per-segment rule ((a)-(d), (f), (g), and the (e) `-c`
    check) to `text`. Shared by the top-level command and by a shell
    heredoc body handed to bash/sh/zsh — a shell script piped that way is
    itself a sequence of commands, not inert data."""
    for seg in split_segments(text):
        tokens = program_tokens(seg)
        if not tokens:
            continue

        # (a) redirection: only the token right after (or attached to) the
        # operator is the target — never a quoted string mentioning one.
        for target in redirect_targets(tokens):
            if is_target(target):
                hits.append(("redirect", seg.strip()))

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

        # (f) dd: only the of= (output) argument is a write target; if= is a read.
        if prog == "dd":
            for t in tokens[1:]:
                if t.startswith("of=") and is_target(t[len("of="):]):
                    hits.append(("dd of=", seg.strip()))

        # (g) install: last positional argument, unless retargeted with -t/--target-directory.
        elif prog == "install":
            has_target_flag = any(
                t == "-t" or t.startswith("--target-directory") for t in tokens[1:]
            )
            if not has_target_flag:
                positionals = [t for t in tokens[1:] if not t.startswith("-")]
                if positionals and is_target(positionals[-1]):
                    hits.append(("install last arg", seg.strip()))

        # (e) python/python3/uv -c "<code>" combining the target with a write call.
        if prog in ("python", "python3", "uv") and "-c" in tokens:
            idx = tokens.index("-c")
            if idx + 1 < len(tokens):
                code = tokens[idx + 1]
                if TARGET in code and has_write_pattern(code):
                    hits.append(("python -c write", seg.strip()))


HEREDOC_START = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?")


def extract_heredocs(text):
    """Return (stripped_text, heredocs). `stripped_text` keeps every line
    except heredoc bodies and their terminator — the `<<MARKER` line itself
    stays, so `cat <<EOF > prompt_plan.md` is still seen by scan_segments.
    Each heredoc is (start_line, marker, body_text, consumer_prog): the
    consumer is the program named before `<<` on the start line."""
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
        consumer_prog = program_name(consumer_tokens)
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


hits = []

stripped_command, heredocs = extract_heredocs(command)
scan_segments(stripped_command, hits)

# Heredoc bodies: a body is only shell commands or interpreter code when the
# thing consuming it is a shell/interpreter. Handed to `git commit -F -`,
# `cat > file`, or `tee`, the body is inert data (a commit message, a note)
# and mentioning `prompt_plan.md` or a redirect in it is not a live write.
for start_line, marker, body, consumer_prog in heredocs:
    if consumer_prog in ("python", "python3", "uv", "perl"):
        if TARGET in body and has_write_pattern(body):
            hits.append(("heredoc write", start_line.strip()))
    elif consumer_prog in ("bash", "sh", "zsh"):
        scan_segments(body, hits)
    # else: a data consumer (git, cat, tee, ...) — body is not inspected.

if hits:
    print("BLOCKED by plan bash write guard (AGENTS.md Harness Enforcement)",
          file=sys.stderr)
    for label, seg in hits:
        print(f"  {label} in: {seg[:200]}", file=sys.stderr)
    print("Edit prompt_plan.md with the Edit tool only.", file=sys.stderr)
    sys.exit(2)

sys.exit(0)
PY
