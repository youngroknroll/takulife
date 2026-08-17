#!/bin/bash
# Git Destructive Guard - PreToolUse hook (matcher: Bash)
#
# Enforces the "stash before a destructive git operation" rule deterministically.
# Two recorded incidents lost uncommitted work here: a `git checkout` used to
# restore a mutated file discarded 24 uncommitted keys, and an earlier restore
# attempt lost work the same way.
#
# Blocks, only when the working tree is dirty (there is something to lose):
#   git reset --hard | git clean -f/-d/-x | git checkout -- <path> | git checkout .
#   git restore <path>   (but not `git restore --staged`, which only unstages)
# Blocks always:
#   git stash clear      (destroys every stash, never a routine step)
#
# A clean tree means these commands cannot destroy uncommitted work, so they pass.
#
# Exit codes: 0 = allow, 2 = block (stderr is fed back to the model)

INPUT=$(cat)

DIRTY_COUNT=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')

python3 - "$INPUT" "${DIRTY_COUNT:-0}" <<'PY'
import json, re, shlex, sys

raw = sys.argv[1] if len(sys.argv) > 1 else ""
try:
    dirty = int(sys.argv[2])
except (IndexError, ValueError):
    dirty = 0

try:
    data = json.loads(raw)
except Exception:
    sys.exit(0)  # unparsable payload: do not block

command = (data.get("tool_input") or {}).get("command") or ""
if "git" not in command:
    sys.exit(0)

segments = [s.strip() for s in re.split(r"\|\||&&|[;|\n]", command) if s.strip()]

# (pattern, label, only_when_dirty)
RULES = [
    (r"\bgit\s+reset\b[^\n]*--hard\b", "git reset --hard", True),
    (r"\bgit\s+clean\b[^\n]*\s-[a-zA-Z]*[fdx]", "git clean -f/-d/-x", True),
    (r"\bgit\s+checkout\b[^\n]*\s--\s", "git checkout -- <path>", True),
    (r"\bgit\s+checkout\s+\.\s*$", "git checkout .", True),
    (r"\bgit\s+restore\b(?![^\n]*--staged)", "git restore <path>", True),
    (r"\bgit\s+stash\s+clear\b", "git stash clear", False),
]

def program(segment):
    """First real token of a segment, ignoring leading VAR=value assignments."""
    try:
        tokens = shlex.split(segment)
    except ValueError:
        tokens = segment.split()
    while tokens and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[0]):
        tokens.pop(0)
    return tokens[0].rsplit("/", 1)[-1] if tokens else ""

hits = []
for seg in segments:
    # Only inspect segments that actually run git; `echo "git reset --hard"`
    # mentions the words but runs echo.
    if program(seg) != "git":
        continue
    for pattern, label, only_dirty in RULES:
        if re.search(pattern, seg):
            if only_dirty and dirty == 0:
                continue
            hits.append((label, seg, only_dirty))

if hits:
    print("BLOCKED by git destructive guard", file=sys.stderr)
    for label, seg, only_dirty in hits:
        print(f"  {label} in: {seg[:160]}", file=sys.stderr)
    if any(o for _, _, o in hits):
        print(f"  working tree has {dirty} uncommitted change(s) that this would discard",
              file=sys.stderr)
    print('  stash first: git stash push -u -m "<why>"  — then retry, then restore',
          file=sys.stderr)
    sys.exit(2)

sys.exit(0)
PY
