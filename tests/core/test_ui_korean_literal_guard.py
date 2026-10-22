"""트랙 43-1 승인 범위 템플릿에는 번역 태그 밖의 한국어 리터럴이 없어야
한다 — 주석·`{% blocktranslate %}`/`{% translate %}` 태그는 번역 대상이므로
제외하고, 남은 텍스트에 한글이 있으면 번역이 빠진 자리다."""
import ast
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

TEMPLATES_DIR = Path(__file__).resolve().parents[2] / "templates"

# 43-1 승인 범위(계획서 §7)의 고정 파일 목록. account/·socialaccount/ 아래는
# 디렉터리 전체가 범위이므로 glob으로 모은다.
_FIXED_RELPATHS = [
    "base.html",
    "404.html",
    "429.html",
    "500.html",
    "core/home.html",
    "core/partials/_site_header.html",
    "core/partials/_topbar.html",
    "core/partials/_site_footer.html",
    "core/partials/_home_collection_snapshot.html",
    "core/partials/_home_event_calendar.html",
    "core/partials/_calendar_grid.html",
    "core/partials/_event_compact_row.html",
    "core/partials/_pager.html",
    "core/partials/_collection_badges.html",
    "core/partials/_auth_field.html",
    "core/partials/_auth_form_errors.html",
    "core/partials/_account_settings_field.html",
    "core/partials/_account_settings_index.html",
    "core/partials/_account_settings_panel_head.html",
    "core/events/list.html",
    "core/events/calendar.html",
    "core/events/detail.html",
]

# 5(셸·오류 페이지·홈) + 14(partials) + 3(events/list·calendar·detail)
# + 16(account/*.html) + 4(account/email/*.txt) + 3(socialaccount/*.html)
# = 45개 — 직접 센 기대 개수 [실측 ls].
_EXPECTED_FILE_COUNT = 45

_COMMENT_TAG_RE = re.compile(r"\{#.*?#\}", re.DOTALL)
_COMMENT_BLOCK_RE = re.compile(r"\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}", re.DOTALL)
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_BLOCKTRANSLATE_RE = re.compile(
    r"\{%\s*blocktranslate\b.*?\{%\s*endblocktranslate\s*%\}", re.DOTALL
)
_TRANSLATE_TAG_RE = re.compile(r"\{%\s*translate\b.*?%\}", re.DOTALL)

_KOREAN_RE = re.compile(r"[가-힣]")
_BRAND_NAME = "타쿠라이프"


def _target_files():
    paths = [TEMPLATES_DIR / relpath for relpath in _FIXED_RELPATHS]
    paths += sorted((TEMPLATES_DIR / "account").glob("*.html"))
    paths += sorted((TEMPLATES_DIR / "account" / "email").glob("*.txt"))
    paths += sorted((TEMPLATES_DIR / "socialaccount").glob("*.html"))
    return paths


def _strip_translated_regions(text):
    text = _COMMENT_TAG_RE.sub("", text)
    text = _COMMENT_BLOCK_RE.sub("", text)
    text = _HTML_COMMENT_RE.sub("", text)
    text = _BLOCKTRANSLATE_RE.sub("", text)
    text = _TRANSLATE_TAG_RE.sub("", text)
    return text.replace(_BRAND_NAME, "")


# I18N-23
def test_승인_범위_템플릿에는_번역_태그_밖의_한국어_리터럴이_없다():
    files = _target_files()
    assert len(files) == _EXPECTED_FILE_COUNT, [f.as_posix() for f in files]

    violations = []
    for path in files:
        stripped = _strip_translated_regions(path.read_text(encoding="utf-8"))
        for lineno, line in enumerate(stripped.splitlines(), start=1):
            if _KOREAN_RE.search(line):
                relpath = path.relative_to(TEMPLATES_DIR).as_posix()
                violations.append(f"{relpath}:{lineno}: {line.strip()[:40]!r}")

    assert violations == []


JS_DIR = Path(__file__).resolve().parents[2] / "static" / "js"

_JS_FIXED_RELPATHS = [
    "shared/account_menu.js",
    "shared/api.js",
    "shared/cta_visibility.js",
    "shared/disclosure.js",
    "shared/error_report.js",
    "shared/i18n_fallback.js",
    "shared/nav_menu.js",
    "shared/status.js",
    "shared/submit_guard.js",
    "shared/theme.js",
    "shared/toast.js",
    "components/confirm-modal.js",
    "components/hscroll.js",
    "pages/home_hero_rotator.js",
    "pages/event_list.js",
]

# shared(11) + components(2) + home_hero_rotator.js(1) + event_list.js(1)
# = 15개 — 직접 센 기대 개수 [실측 ls].
_EXPECTED_JS_FILE_COUNT = 15

_BLOCK_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_UNESCAPED_QUOTE_RE = re.compile(r"(?<!\\)['\"]")
_GETTEXT_CALL_RE = re.compile(
    r"\b(?:gettext|ngettext)\(\s*"
    r"((?:'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\")"
    r"(?:\s*,\s*(?:'(?:\\.|[^'\\])*'|\"(?:\\.|[^\"\\])*\"))?)"
)


def _strip_block_comments(text):
    return _BLOCK_COMMENT_RE.sub("", text)


def _strip_line_comments(text):
    """그 줄에서 `//` 앞의 따옴표 개수가 짝수일 때만 그 지점을 줄 끝
    주석으로 보고 잘라낸다 — 문자열 리터럴 안의 `//`를 오인하지 않는다."""
    stripped_lines = []
    for line in text.splitlines():
        search_from = 0
        while True:
            idx = line.find("//", search_from)
            if idx == -1:
                break
            quote_count = len(_UNESCAPED_QUOTE_RE.findall(line[:idx]))
            if quote_count % 2 == 0:
                line = line[:idx]
                break
            search_from = idx + 2
        stripped_lines.append(line)
    return "\n".join(stripped_lines)


def _strip_gettext_string_args(text):
    def _drop_captured_strings(match):
        return text[match.start() : match.start(1)]

    return _GETTEXT_CALL_RE.sub(_drop_captured_strings, text)


def _js_target_files():
    return [JS_DIR / relpath for relpath in _JS_FIXED_RELPATHS]


# I18N-24
def test_승인_범위_JS에는_gettext_밖의_한국어_리터럴이_없다():
    files = _js_target_files()
    assert len(files) == _EXPECTED_JS_FILE_COUNT, [f.as_posix() for f in files]

    violations = []
    for path in files:
        text = _strip_block_comments(path.read_text(encoding="utf-8"))
        text = _strip_line_comments(text)
        text = _strip_gettext_string_args(text)
        for lineno, line in enumerate(text.splitlines(), start=1):
            if _KOREAN_RE.search(line):
                relpath = path.relative_to(JS_DIR).as_posix()
                violations.append(f"{relpath}:{lineno}: {line.strip()[:40]!r}")

    assert violations == []


# E-04 — 뷰 코드의 한국어 문자열은 번역 함수의 인자이거나 독스트링이어야 한다.
EVENTS_VIEW_PATH = Path(__file__).resolve().parents[2] / "web" / "views" / "events.py"

_GETTEXT_FUNCTION_NAMES = frozenset(
    {"gettext", "gettext_lazy", "ngettext", "npgettext", "pgettext", "_"}
)


def _called_function_name(call):
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    return None


def _exempt_string_nodes(tree):
    """독스트링과 번역 함수 호출의 문자열 상수 위치 인자(msgid·복수형·
    msgctxt)는 검사에서 뺀다 — 나머지 한국어 문자열이 번역 누락이다."""
    exempt = set()
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                exempt.add(id(body[0].value))
        if (
            isinstance(node, ast.Call)
            and _called_function_name(node) in _GETTEXT_FUNCTION_NAMES
        ):
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    exempt.add(id(arg))
    return exempt


# E-04
def test_이벤트_뷰_코드에는_번역_함수_밖의_한국어_문자열_상수가_없다():
    tree = ast.parse(EVENTS_VIEW_PATH.read_text(encoding="utf-8"))
    exempt = _exempt_string_nodes(tree)

    violations = [
        f"{node.lineno}:{node.value.strip()[:40]!r}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in exempt
        and _KOREAN_RE.search(node.value)
    ]

    assert violations == []
