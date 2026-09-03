#!/bin/bash
# Plan Number Tag Guard - PreToolUse hook (matcher: Edit|Write)
#
# Enforces AGENTS.md "Numbers In Documents" and "Orchestrator Contract":
# every number written into a document must name its unit and say whether it
# was measured or read (a source tag), and must be re-measured before it
# sizes any work. This hook checks new text going into `prompt_plan.md` only.
#
# Blocks:
#   - a paragraph (blank-line separated block) that contains a count with a
#     quantity unit (건/개/회/행/줄/쿼리/초/ms/B/바이트/KB/MB/명/토큰/%/배/
#     곳/번/파일/워커/스레드/연결) where the numeric value is 2 or more, and
#     the same paragraph has none of the source tags [실측]/[코드]/[계산]/
#     [문서]/[대시보드].
# Allows:
#   - the same paragraph carrying one of the source tags
#   - values of 0 or 1 (design description, e.g. "1회")
#   - dates, line numbers (`:112`), PR numbers (`#325`), decimals (`5.2`),
#     and bare identifiers (`S1`, `§3-15`, `v2`) since no unit follows them
#   - files other than `prompt_plan.md`
#   - unparsable JSON payloads
#
# Exit codes: 0 = allow, 2 = block (stderr is fed back to the model)

INPUT=$(cat)

python3 - "$INPUT" <<'PY'
import json, os, re, sys

raw = sys.argv[1] if len(sys.argv) > 1 else ""
try:
    data = json.loads(raw)
except Exception:
    sys.exit(0)  # unparsable payload: do not block

path = (data.get("tool_input") or {}).get("file_path") or ""
if not path or os.path.basename(path) != "prompt_plan.md":
    sys.exit(0)

tool_input = data.get("tool_input") or {}
tool_name = data.get("tool_name") or ""

if tool_name == "Edit":
    text = tool_input.get("new_string")
elif tool_name == "Write":
    text = tool_input.get("content")
else:
    text = tool_input.get("new_string")
    if text is None:
        text = tool_input.get("content")

if text is None:
    sys.exit(0)

UNITS = ("건", "개", "회", "행", "줄", "쿼리", "초", "ms", "B", "바이트", "KB",
          "MB", "명", "토큰", "%", "배", "곳", "번", "파일", "워커", "스레드",
          "연결")
UNIT_PATTERN = "|".join(re.escape(u) for u in UNITS)
NUMBER_RE = re.compile(
    r"(?<![\d.\-/:#])(\d{1,3}(?:,\d{3})*|\d+)\s*(?:" + UNIT_PATTERN + r")(?![A-Za-z])"
)
TAGS = ("[실측", "[코드", "[계산", "[문서", "[대시보드")

# Blank-line separated blocks (blank = whitespace-only line). A markdown
# table's rows have no blank line between them, so they stay one block.
blocks = re.split(r"\n\s*\n", text)

violations = []
for block in blocks:
    if not block.strip():
        continue
    matches = []
    for m in NUMBER_RE.finditer(block):
        value = int(m.group(1).replace(",", ""))
        if value >= 2:
            matches.append(m.group(0).strip())
    if not matches:
        continue
    if any(tag in block for tag in TAGS):
        continue
    first_line = block.strip().splitlines()[0][:60]
    violations.append((first_line, matches))

if violations:
    print("BLOCKED by plan number tag guard (AGENTS.md Numbers In Documents / "
          "Orchestrator Contract)", file=sys.stderr)
    for first_line, matches in violations:
        print(f"  block: {first_line}", file=sys.stderr)
        print(f"  numbers: {', '.join(matches)}", file=sys.stderr)
    print("Add [실측]/[코드]/[계산]/[문서]/[대시보드] in the same paragraph, "
          "or rewrite the number.", file=sys.stderr)
    sys.exit(2)

sys.exit(0)
PY
