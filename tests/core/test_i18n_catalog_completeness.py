"""locale/*/LC_MESSAGES/*.po 번역 완결성 검사. 새 의존성(polib 등) 없이
이 모듈 안에 작은 .po 파서를 직접 둔다."""
import re
from collections import Counter
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

LOCALE_DIR = Path(__file__).resolve().parents[2] / "locale"

EXPECTED_PO_RELPATHS = sorted(
    [
        "en/LC_MESSAGES/django.po",
        "en/LC_MESSAGES/djangojs.po",
        "ja/LC_MESSAGES/django.po",
        "ja/LC_MESSAGES/djangojs.po",
        "zh_Hans/LC_MESSAGES/django.po",
        "zh_Hans/LC_MESSAGES/djangojs.po",
    ]
)

# %(name)s / %s / %d 스타일(Python)과 {name} 스타일(str.format) 자리표시자.
_PLACEHOLDER_RE = re.compile(r"%\(\w+\)s|%s|%d|\{\w+\}")
# 여는/닫는 HTML 태그 전체 문자열(속성 포함) — 번역가가 태그를 글자 그대로
# 보존해야 한다. 이름만 비교하면 속성 주입(예: onmouseover 추가)을 놓친다.
_TAG_RE = re.compile(r"</?[a-zA-Z][^<>]*>")

_KEYWORD_RE = re.compile(r'^(msgctxt|msgid_plural|msgid|msgstr(\[(\d+)\])?)\s+"(.*)"$')
_CONTINUATION_RE = re.compile(r'^"(.*)"$')
_ESCAPE_RE = re.compile(r"\\(.)")
_ESCAPE_MAP = {"n": "\n", "t": "\t", '"': '"', "\\": "\\"}


def _unescape(raw):
    return _ESCAPE_RE.sub(lambda m: _ESCAPE_MAP.get(m.group(1), m.group(1)), raw)


def _po_files():
    return sorted(LOCALE_DIR.glob("*/LC_MESSAGES/*.po"), key=lambda p: p.as_posix())


def _relpath(path):
    return path.relative_to(LOCALE_DIR).as_posix()


def _new_entry():
    return {"msgctxt": None, "msgid": None, "msgid_plural": None, "msgstrs": {}, "flags": set()}


def _parse_po(path):
    """msgctxt·msgid·msgid_plural·msgstr/msgstr[n]·여러 줄 이어붙이기·#, 플래그를
    처리하고 #~ 폐기 항목은 통째로 건너뛴다. 각 항목은
    {msgctxt, msgid, msgid_plural, msgstrs(list), flags(set)} dict다."""
    entries = []
    current = None
    field = None  # ("msgctxt",) / ("msgid",) / ("msgid_plural",) / ("msgstr", idx)

    def finalize():
        nonlocal current
        if current is not None and current["msgid"] is not None:
            ordered_msgstrs = [current["msgstrs"][key] for key in sorted(current["msgstrs"])]
            entries.append(
                {
                    "msgctxt": current["msgctxt"],
                    "msgid": current["msgid"],
                    "msgid_plural": current["msgid_plural"],
                    "msgstrs": ordered_msgstrs,
                    "flags": current["flags"],
                }
            )
        current = None

    lines = path.read_text(encoding="utf-8").splitlines()
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i].strip()
        if line == "":
            finalize()
            field = None
            i += 1
            continue
        if line.startswith("#~"):
            # 폐기(obsolete) 항목 — 다음 빈 줄까지 통째로 건너뛴다.
            i += 1
            while i < n and lines[i].strip() != "":
                i += 1
            current = None
            field = None
            continue
        if line.startswith("#,"):
            current = current or _new_entry()
            for flag in line[2:].split(","):
                flag = flag.strip()
                if flag:
                    current["flags"].add(flag)
            i += 1
            continue
        if line.startswith("#"):
            i += 1
            continue
        match = _KEYWORD_RE.match(line)
        if match:
            current = current or _new_entry()
            keyword, _bracket, index, text = match.groups()
            value = _unescape(text)
            if keyword == "msgctxt":
                current["msgctxt"] = value
                field = ("msgctxt",)
            elif keyword == "msgid":
                current["msgid"] = value
                field = ("msgid",)
            elif keyword == "msgid_plural":
                current["msgid_plural"] = value
                field = ("msgid_plural",)
            else:
                idx = int(index) if index is not None else 0
                current["msgstrs"][idx] = value
                field = ("msgstr", idx)
            i += 1
            continue
        match = _CONTINUATION_RE.match(line)
        if match and current is not None and field is not None:
            piece = _unescape(match.group(1))
            if field[0] == "msgctxt":
                current["msgctxt"] += piece
            elif field[0] == "msgid":
                current["msgid"] += piece
            elif field[0] == "msgid_plural":
                current["msgid_plural"] += piece
            elif field[0] == "msgstr":
                current["msgstrs"][field[1]] += piece
            i += 1
            continue
        i += 1

    finalize()
    return entries


# I18N-14a
def test_po_파일에는_빈_msgstr나_fuzzy_항목이_없다():
    files = _po_files()
    assert [_relpath(f) for f in files] == EXPECTED_PO_RELPATHS

    violations = []
    for file in files:
        relpath = _relpath(file)
        for entry in _parse_po(file):
            is_header = entry["msgid"] == ""
            if "fuzzy" in entry["flags"]:
                violations.append(f"{relpath}: {entry['msgid'][:40]!r} (fuzzy)")
                continue
            if is_header:
                continue
            if not entry["msgstrs"] or any(not msgstr for msgstr in entry["msgstrs"]):
                violations.append(f"{relpath}: {entry['msgid'][:40]!r} (empty msgstr)")

    assert violations == []


# I18N-14b
def test_po_번역문의_자리표시자는_원문과_이름이_같다():
    files = _po_files()
    assert [_relpath(f) for f in files] == EXPECTED_PO_RELPATHS

    checked = 0
    violations = []
    for file in files:
        relpath = _relpath(file)
        for entry in _parse_po(file):
            if entry["msgid"] == "":
                continue
            msgid_tokens = Counter(_PLACEHOLDER_RE.findall(entry["msgid"]))
            for msgstr in entry["msgstrs"]:
                if not msgstr:
                    continue
                checked += 1
                if Counter(_PLACEHOLDER_RE.findall(msgstr)) != msgid_tokens:
                    violations.append(f"{relpath}: {entry['msgid'][:40]!r}")

    assert checked > 0
    assert violations == []


# I18N-14c
def test_po_번역문의_HTML_태그는_원문과_같다():
    """태그 이름뿐 아니라 속성까지 포함해 원문과 글자 그대로 같아야 한다
    — 속성 주입(예: onmouseover 추가)은 `blocktranslate`·`mark_safe`로
    HTML 그대로 렌더되는 경로에서 XSS 표면이 된다."""
    files = _po_files()
    assert [_relpath(f) for f in files] == EXPECTED_PO_RELPATHS

    checked = 0
    violations = []
    for file in files:
        relpath = _relpath(file)
        for entry in _parse_po(file):
            if entry["msgid"] == "":
                continue
            msgid_tags = Counter(_TAG_RE.findall(entry["msgid"]))
            for msgstr in entry["msgstrs"]:
                if not msgstr:
                    continue
                checked += 1
                if Counter(_TAG_RE.findall(msgstr)) != msgid_tags:
                    violations.append(f"{relpath}: {entry['msgid'][:40]!r}")

    assert checked > 0
    assert violations == []
