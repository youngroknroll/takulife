#!/bin/bash
# Git Commit Style Guard - PreToolUse hook (matcher: Bash)
#
# Enforces AGENTS.md "Python Style Guide" at commit time: .py files that go into
# a commit must pass ruff check and ruff format --check (project configuration).
#
# Checked set (PreToolUse runs before the command, so the index may still be
# empty for `git add x.py && git commit`):
#   (a) .py files already staged
#   (b) .py paths given to any `git add` segment of the same command (globs
#       expanded, existing files only); `-A/--all/-u/--update/.` adds every
#       modified, added or untracked .py reported by `git status`
#   (c) .py pathspecs given directly to `git commit` (after `--` or as plain args)
#
# Blocks:
#   - `git commit ...` (incl. `-C <dir>` / `-c k=v` before it) when a file in the
#     checked set has a ruff violation or format difference
# Allows:
#   - non-commit commands, commits whose checked set is empty
#   - files excluded by pyproject.toml (migrations/; --force-exclude applies it)
#   - ruff/uv missing or slower than 10 s (warning only)
#
# Known gaps: ruff inspects the WORKING-TREE file, not the staged blob, so a
# file whose staged and working-tree contents differ can be judged wrongly;
# globs inside quotes are expanded but shell variables, command substitution
# and `bash -c` nesting are not; segment splitting also splits on separators
# inside quotes; `git add -p`/directory arguments are not expanded.
# a file created by the same command (`printf > new.py; git add new.py && git commit`)
# does not exist yet at PreToolUse time, so it is skipped (inherent limit).
#
# Exit codes: 0 = allow, 2 = block (stderr is fed back to the model)

INPUT=$(cat)

python3 - "$INPUT" <<'PY'
import glob, json, os, re, shlex, subprocess, sys

raw = sys.argv[1] if len(sys.argv) > 1 else ""
try:
    data = json.loads(raw)
except Exception:
    sys.exit(0)  # unparsable payload: do not block

command = (data.get("tool_input") or {}).get("command") or ""
if not command.strip():
    sys.exit(0)

segments = [s for s in re.split(r"\|\||&&|[;|\n]", command) if s.strip()]
COMMIT_VALUE_OPTS = {"-m", "-F", "-C", "-c", "-t", "--message", "--file", "--author",
                     "--date", "--template", "--reuse-message", "--reedit-message",
                     "--fixup", "--squash", "--cleanup", "--trailer"}
ADD_ALL = {"-A", "--all", "-u", "--update", "."}

def parse(segment):
    """Return (subcommand, args, c_dir) for a git segment, else None."""
    try:
        tokens = shlex.split(segment)
    except ValueError:
        tokens = segment.split()
    while tokens and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[0]):
        tokens.pop(0)
    if not tokens or tokens[0].rsplit("/", 1)[-1] != "git":
        return None
    rest, c_dir = tokens[1:], ""
    while rest and rest[0] in ("-C", "-c") and len(rest) > 1:
        if rest[0] == "-C":
            c_dir = rest[1]
        rest = rest[2:]  # skip option and its value
    if not rest:
        return None
    return rest[0], rest[1:], c_dir

parsed = [p for p in (parse(s) for s in segments) if p]
if not any(sub == "commit" for sub, _, _ in parsed):
    sys.exit(0)

root = os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or ""
if not root:
    sys.exit(0)

def git_lines(args):
    try:
        out = subprocess.run(["git"] + args, cwd=root, capture_output=True, text=True,
                             timeout=10).stdout
    except Exception:
        return []
    return out.split("\n")

def resolve(arg, c_dir):
    # existing .py files for a path or glob, relative to the root (or -C dir)
    base = os.path.join(root, c_dir) if c_dir else root
    pattern = arg if os.path.isabs(arg) else os.path.join(base, arg)
    return [os.path.relpath(p, root) for p in glob.glob(pattern)
            if p.endswith(".py") and os.path.isfile(p)]

found = {f for f in git_lines(["diff", "--cached", "--name-only", "--diff-filter=ACMR",
                               "--", "*.py"]) if f.strip()}
for sub, args, c_dir in parsed:
    if sub == "add":
        if any(a in ADD_ALL for a in args):
            for line in git_lines(["status", "--porcelain", "--untracked-files=all"]):
                path = line[3:].split(" -> ")[-1].strip().strip('"')
                if line[:2].strip() != "D" and path.endswith(".py"):
                    found.update(resolve(path, ""))
        for a in args:
            if not a.startswith("-"):
                found.update(resolve(a, c_dir))
    elif sub == "commit":
        skip, after_dd = False, False
        for a in args:
            if skip:
                skip = False
            elif after_dd:
                found.update(resolve(a, c_dir))
            elif a == "--":
                after_dd = True
            elif a in COMMIT_VALUE_OPTS:
                skip = True
            elif not a.startswith("-"):
                found.update(resolve(a, c_dir))
files = sorted(found)
if not files:
    sys.exit(0)

base = ["uv", "run", "--no-sync", "ruff"]
commands = [
    base + ["check", "--force-exclude", "--no-fix", "--output-format", "concise"] + files,
    base + ["format", "--check", "--force-exclude"] + files,
]
output = []
failed = False
for cmd in commands:
    try:
        proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=10)
    except subprocess.TimeoutExpired:
        print("git-commit-style-guard: ruff timed out, skipped", file=sys.stderr)
        sys.exit(0)
    except OSError:
        print("git-commit-style-guard: ruff unavailable, skipped", file=sys.stderr)
        sys.exit(0)
    text = (proc.stdout or "") + (proc.stderr or "")
    if proc.returncode in (126, 127) or "Failed to spawn" in text:
        print("git-commit-style-guard: ruff unavailable, skipped", file=sys.stderr)
        sys.exit(0)
    if proc.returncode != 0:
        failed = True
        output.extend(text.splitlines())

if failed:
    print("BLOCKED by git commit style guard (AGENTS.md Python Style Guide)", file=sys.stderr)
    for line in output[:40]:
        print(line, file=sys.stderr)
    print("Fix or unstage the files above. Format: uv run ruff format <files>",
          file=sys.stderr)
    sys.exit(2)

sys.exit(0)
PY
