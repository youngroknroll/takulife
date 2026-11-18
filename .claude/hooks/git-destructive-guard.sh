#!/bin/bash
# Git Destructive Guard - PreToolUse hook (matcher: Bash)
#
# Enforces the "stash before a destructive git operation" rule deterministically.
# Two recorded incidents lost uncommitted work here: a `git checkout` used to
# restore a mutated file discarded 24 uncommitted keys, and an earlier restore
# attempt lost work the same way.
#
# Blocks, only when the working tree is dirty (there is something to lose):
#   git reset --hard | git clean -f/-d/-x/--force (not when -n/--dry-run is
#     present, since nothing is actually deleted) | git checkout <path> (with or
#     without a leading `--`; a positional with no `--` counts as a path
#     only when it names something that exists on disk at the process's
#     cwd — an unknown name is a branch/commit, not a path)
#   git restore <path>   (but not `git restore --staged`, which only unstages)
# Blocks always:
#   git stash clear      (destroys every stash, never a routine step)
#   git clean -x/-X      (removes ignored files even on a clean tree, not when
#     -n/--dry-run is present)
#
# A clean tree means these commands cannot destroy uncommitted work, so they pass.
# A global option before the subcommand (`-C <dir>`, `-c <k=v>`, ...) no
# longer hides `reset`/`clean`/`checkout`/`restore` from the rules above —
# see `skip_git_global_options` below (same approach as git-stage-all-guard.sh).
#
# Exit codes: 0 = allow, 2 = block (stderr is fed back to the model)

INPUT=$(cat)

DIRTY_COUNT=$(git status --porcelain 2>/dev/null | wc -l | tr -d ' ')

python3 - "$INPUT" "${DIRTY_COUNT:-0}" <<'PY'
import json, os, re, shlex, sys

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

cwd = data.get("cwd") or os.getcwd()

segments = [s.strip() for s in re.split(r"\|\||&&|[;|\n]", command) if s.strip()]


def program_tokens(segment):
    """First real token stream of a segment, ignoring leading VAR=value
    assignments."""
    try:
        tokens = shlex.split(segment)
    except ValueError:
        tokens = segment.split()
    while tokens and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", tokens[0]):
        tokens.pop(0)
    return tokens


# `-C <dir>`과 `-c <k=v>`처럼 서브커맨드 앞에 오는 전역 옵션을 건너뛰어야
# `git -C . reset --hard`도 `reset`으로 인식한다(git-stage-all-guard.sh와 동일).
GLOBAL_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix"}
GLOBAL_FLAG_OPTS = {
    "--no-pager", "-p", "--paginate", "-P", "--bare", "--no-replace-objects",
    "--literal-pathspecs", "--glob-pathspecs", "--noglob-pathspecs",
    "--icase-pathspecs", "--no-optional-locks",
}


def skip_git_global_options(tokens):
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if not tok.startswith("-"):
            break
        if tok in GLOBAL_VALUE_OPTS:
            i += 2
            continue
        if any(tok.startswith(opt + "=") for opt in GLOBAL_VALUE_OPTS):
            i += 1
            continue
        if tok in GLOBAL_FLAG_OPTS:
            i += 1
            continue
        break
    return tokens[i:]


def path_exists_at_cwd(token):
    token = token.strip().strip("'\"")
    path = token if os.path.isabs(token) else os.path.join(cwd, token)
    return os.path.exists(path)


def checkout_targets_path(rest):
    """`--` 뒤 인자는 무조건 경로로 보고, `--`가 없으면 디스크에 실제 존재하는
    포지셔널만 경로로 본다 — 없는 이름은 브랜치·커밋으로 본다."""
    if "--" in rest:
        after = rest[rest.index("--") + 1:]
        return bool(after)
    positionals = [t for t in rest if not t.startswith("-")]
    return any(path_exists_at_cwd(t) for t in positionals)


IGNORED_FILES_LABEL = "git clean -x/-X (removes ignored files)"


def clean_dry_run(rest):
    """`--dry-run`이나 결합 플래그 포함 `-n`이 있으면 실제로 지우지 않는다."""
    return any(
        t == "--dry-run" or (t.startswith("-") and not t.startswith("--") and "n" in t[1:])
        for t in rest
    )


def clean_is_destructive(rest):
    """결합 플래그(`-fd`)까지 포함해 f/d/x로 끝나는 단일 대시 플래그나
    `--force`가 있고, `-n`/`--dry-run`(결합 플래그 포함)이 없을 때만 실제로
    지운다."""
    destructive = any(
        re.fullmatch(r"-[a-zA-Z]*[fdx]", t) for t in rest if t.startswith("-") and not t.startswith("--")
    ) or "--force" in rest
    return destructive and not clean_dry_run(rest)


def clean_removes_ignored(rest):
    """단일 대시 플래그에 `x`/`X`가 있고 dry-run이 아니면, 더티 여부와
    무관하게 무시 파일을 지운다."""
    has_x = any(
        t.startswith("-")
        and not t.startswith("--")
        and ("x" in t[1:] or "X" in t[1:])
        for t in rest
    )
    return has_x and not clean_dry_run(rest)


hits = []
for seg in segments:
    tokens = program_tokens(seg)
    if not tokens:
        continue
    prog = tokens[0].rsplit("/", 1)[-1]
    if prog != "git":
        continue
    after_global = skip_git_global_options(tokens[1:])
    sub = after_global[0] if after_global else ""
    rest = after_global[1:]

    if sub == "reset":
        if "--hard" in rest and dirty > 0:
            hits.append(("git reset --hard", seg, True))
    elif sub == "clean":
        if clean_is_destructive(rest) and dirty > 0:
            hits.append(("git clean -f/-d/-x/--force", seg, True))
        if clean_removes_ignored(rest):
            hits.append((IGNORED_FILES_LABEL, seg, False))
    elif sub == "checkout":
        if checkout_targets_path(rest) and dirty > 0:
            hits.append(("git checkout <path>", seg, True))
    elif sub == "restore":
        if "--staged" not in rest and dirty > 0:
            hits.append(("git restore <path>", seg, True))
    elif sub == "stash":
        if rest[:1] == ["clear"]:
            hits.append(("git stash clear", seg, False))

if hits:
    print("BLOCKED by git destructive guard", file=sys.stderr)
    for label, seg, only_dirty in hits:
        print(f"  {label} in: {seg[:160]}", file=sys.stderr)
    if any(o for _, _, o in hits):
        print(f"  working tree has {dirty} uncommitted change(s) that this would discard",
              file=sys.stderr)
    if any(label == IGNORED_FILES_LABEL for label, _, _ in hits):
        print("  ignored files are not saved by git stash -u: drop -x/-X, or preview with -n first",
              file=sys.stderr)
    if any(label != IGNORED_FILES_LABEL for label, _, _ in hits):
        print('  stash first: git stash push -u -m "<why>"  — then retry, then restore',
              file=sys.stderr)
    sys.exit(2)

sys.exit(0)
PY
