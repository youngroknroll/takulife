"""가드: 추적 파일의 주석·독스트링 줄은 한글이 없는 영어 산문이면 위반이다.

AGENTS.md "Code Comment Policy"(주석은 한국어로 쓴다, 식별자·경로 등 코드
표기는 원문 유지)가 산문으로만 존재해 검토자가 놓친 사고(같은 주에 영어
주석 82줄 통과)를 재발시키지 않으려고 만든 계약 가드다.

스캔 대상: `git ls-files`를 직접 호출해 얻는다. 처음엔 파일시스템 rglob +
손유지 제외 목록으로 만들었었는데 두 가지 이유로 버렸다.
1. ".git이 CI에 없을 수 있다"는 애초의 회피 근거가 틀렸다 — 이 저장소
   `.github/workflows/ci.yml`의 체크아웃 단계(`actions/checkout@v4`,
   fetch-depth·sparse·filter 지정 없음)는 전체 `.git`을 그대로 남긴다.
2. 손유지 제외 목록 방식은 "가드 자신처럼 아직 `git add`되지 않은 파일"이
   하나만 있어도 동치성 검사가 깨져 정상 작업 흐름을 벌한다. `git
   ls-files`를 직접 쓰면 그 동치성 검사 자체가 필요 없어진다(제외 목록을
   손으로 맞출 대상이 사라지므로).
git 호출이 실패하거나 대상이 0개면 `subprocess.run(..., check=True)`와
빈 목록 assert로 시끄럽게 실패시킨다 — 스캔 대상 0개를 조용히 통과시키면
가드가 죽은 채로 방치된다.

대상 확장자: `.py .css .js .html`. `migrations/`는 역사적 스냅샷이라 제외.

주석·독스트링 추출 방식:
- `.py`: `tokenize`로 `#` 주석을, `ast`로 모듈·클래스·함수의 첫 문장이
  문자열 리터럴인 독스트링을 찾는다.
- `.css`: `/* ... */`.
- `.js`: `/* ... */`와 줄 끝까지의 `//`. `//`가 문자열 리터럴 안(예:
  `"http://..."`)인지는 그 줄에서 `//` 앞의 따옴표 개수 홀짝으로만
  판정하는 얕은 휴리스틱이다 — 여러 줄에 걸친 문자열이나 템플릿 리터럴은
  놓칠 수 있다.
- `.html`: `<!-- ... -->`, Django `{# ... #}`, `{% comment %}...{%
  endcomment %}`.

판정 로직(`_is_violation_line`) — "포함 여부"가 아니라 "코드를 걷어내고
남은 것이 문장인가"로 판정한다. 첫 버전(영어 기능어 2개 이상 + 코드 신호
개수와 비교)은 실제 스윕 표본으로 대조하니 산문의 1/3을 놓쳤다 — 이
저장소 주석은 거의 다 `transaction.on_commit`, `create_user(password=None)`
같은 식별자를 언급해서, "코드 신호가 있으면 통과"라는 규칙 자체가 너무
관대했다. 그래서 순서를 뒤집었다:
1. 구조 구분선(`─`/`═`), 도구 지시어(`#!`, `# type:`, `# noqa`,
   `# pragma`, `@ts-`, `eslint-`)가 있으면 줄 전체를 통과시킨다 — 이들은
   언어가 아니라 형식이다.
2. `:=` `=>` `==` `!=` `::` 같은 코드 전용 연산자가 있으면 통과시킨다 —
   이 저장소 표본에서 이 연산자들은 예외 없이 코드 표현식(왈러스 대입식
   등) 안에서만 나타났다.
3. `TODO(<범위>):`, `except-ok:` 마커는 **마커 문자열 자체만** 지우고
   나머지는 그대로 판정을 계속한다 — 마커는 형식이라 유지하되 뒤에 오는
   사유는 한국어여야 한다는 정책을 그대로 지킨다(첫 버전은 마커가 보이면
   줄 전체를 통과시켜 영어 사유가 새어 나갔다).
4. 남은 텍스트에 한글이 한 글자라도 있으면 통과.
5. 남은 텍스트에서 코드 토큰(백틱 span, `{% %}`/`{{ }}`/`{# #}`,
   HTML/XML 태그, 엔티티 참조, 따옴표로 감싼 문자열, `함수(...)` 호출
   표기, 점 표기 경로, snake_case, camelCase, `4px`/`44px` 같은 숫자+단위,
   `min-height` 같은 하이픈 복합어, `/a/b/` 슬래시 경로, `WCAG`처럼 3자
   이상 ALLCAPS 토큰)를 공백으로 지운다.
6. 지우고 남은 텍스트에서 영어 기능어(브리프가 제시한 목록)가 1개 이상,
   그리고 남은 영어 단어 총수가 4개 이상이면 위반이다. 둘 다 오라클
   대조로 정한 문턱값이다 — 기능어 2개 이상을 요구했던 첫 버전은
   "No password requested: create_user(password=None) makes an"처럼
   대문자로 시작하거나 흔한 기능어를 안 쓰는 문장을 놓쳤다.

이 로직은 `/private/tmp/.../scratchpad/guard_oracle.py`의 실제 스윕
표본(위반 15줄 + 예외 24줄, 이 저장소에서 실제로 있었던 줄)을 놓침 0 /
오탐 0으로 통과한다(구현자가 직접 대조 확인, 근거는 핸드오프 보고 참고).
그 오라클은 스크래치패드에 있어 이 저장소에 커밋되지 않으므로, 오라클의
대표 사례를 아래 `test_예외로_통과해야_하는_코드_표기_실물은_위반이_아니다`
/ `test_오라클에서_가져온_실제_영어_산문_표본은_위반으로_잡힌다`로 옮겨
심어 회귀를 고정한다.

주석 길이 규칙(1~2줄)은 이번 가드로 강제하지 않는다 — 코디네이터가 보고한
실측치로는 2줄을 넘는 주석이 1,215개(44%)이고, 정책 자체가 "넘으면
개조식으로 압축해도 된다"는 예외를 두는데 개조식 여부는 기계로 판별할 수
없다. 이 1,215개/44% 수치는 코디네이터가 전달한 것을 그대로 인용한 것이며
이 작업자가 직접 재측정하지 않았다 — 이 규칙에 강제력을 부여하려는
사람은 먼저 이 수치를 재측정해야 한다.

한계: 문자열 리터럴 안에 우연히 주석처럼 보이는 텍스트가 있어도 걸러내지
않는 얕은 정규식/토큰 기반 스캔이다. f-string 안의 `#`, 멀티라인 JS
템플릿 리터럴 안의 `//`는 오탐/누락 여지가 있다 — 이번 스윕 대상 저장소
코드에서는 그런 사례가 실측되지 않았다.
"""
import ast
import io
import re
import subprocess
import tokenize
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SCANNED_EXTENSIONS = (".py", ".css", ".js", ".html")

HANGUL_RE = re.compile(r"[가-힣]")
STRUCTURAL_SEPARATOR_RE = re.compile(r"[─═]")
TOOL_DIRECTIVE_RE = re.compile(r"#!|#\s*type:|#\s*noqa|#\s*pragma|@ts-|eslint-")
CODE_SYNTAX_OPERATOR_RE = re.compile(r":=|=>|==|!=|::")
MARKER_RE = re.compile(r"except-ok:\s*|TODO\([^)]*\):\s*", re.IGNORECASE)

FUNCTION_WORDS = (
    "the a an is are to of and or that this when if not for with so but as "
    "it in on at by from has have can should would will only also there "
    "which what how because since while do does did they them their we you "
    "our its"
).split()
FUNCTION_WORD_RE = re.compile(r"\b(" + "|".join(FUNCTION_WORDS) + r")\b", re.IGNORECASE)

# 순서대로 적용해 원문에서 코드 표기를 공백으로 지운다 — 남는 텍스트가
# 문장으로 성립하는지가 최종 판정 대상이다.
CODE_STRIP_PATTERNS = (
    re.compile(r"`[^`]*`"),  # 백틱 코드 span
    re.compile(r"\{%.*?%\}|\{\{.*?\}\}|\{#.*?#\}"),  # 템플릿 태그
    re.compile(r"<!\w[^>]*>|</?[a-zA-Z][^>]*>"),  # html/xml 태그(<!ENTITY ...> 포함)
    re.compile(r"&\w+;"),  # 엔티티 참조
    re.compile(r'"[^"]*"|\'[^\']*\''),  # 따옴표로 감싼 문자열(경로·코드 리터럴)
    re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*\([^()]*\)"),  # 함수(...) 호출 표기
    re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+\b"),  # 점.표기.경로
    re.compile(r"\b[A-Za-z][A-Za-z0-9]*_[A-Za-z0-9_]*\b"),  # snake_case
    re.compile(r"\b[a-z]+[A-Z][A-Za-z0-9]*\b"),  # camelCase
    re.compile(r"~?\d+(?:\.\d+)?(?:px|rem|em|%|s|ms)\b", re.IGNORECASE),  # 숫자+단위
    re.compile(r"\b[a-z]+(?:-[a-z]+)+\b"),  # 하이픈 복합 토큰(CSS 속성 등)
    re.compile(r"\b[\w.\-]+/[\w.\-/]+\b"),  # /a/b 슬래시 경로
    re.compile(r"\b[A-Z][A-Z0-9_]{2,}\b"),  # 3자 이상 ALLCAPS 상수/약어
)

MIN_FUNCTION_WORD_HITS = 1
MIN_REMAINING_WORDS = 4


def _strip_code_tokens(text):
    for pattern in CODE_STRIP_PATTERNS:
        text = pattern.sub(" ", text)
    return text


def _is_violation_line(text):
    """한 줄의 주석/독스트링 텍스트가 한글 없는 영어 산문이면 True."""
    if STRUCTURAL_SEPARATOR_RE.search(text):
        return False
    if TOOL_DIRECTIVE_RE.search(text):
        return False
    if CODE_SYNTAX_OPERATOR_RE.search(text):
        return False

    text = MARKER_RE.sub(" ", text)
    if HANGUL_RE.search(text):
        return False

    stripped = _strip_code_tokens(text)
    function_word_hits = {match.lower() for match in FUNCTION_WORD_RE.findall(stripped)}
    if len(function_word_hits) < MIN_FUNCTION_WORD_HITS:
        return False

    remaining_words = re.findall(r"[A-Za-z']+", stripped)
    if len(remaining_words) < MIN_REMAINING_WORDS:
        return False

    return True


def _iter_scanned_files(root):
    """`git ls-files`로 추적 파일 목록을 얻어 확장자 필터링 + migrations/ 제외만 적용한다."""
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    )
    tracked_paths = [line for line in result.stdout.splitlines() if line]
    # `git ls-files`는 인덱스를 보므로 아직 스테이지되지 않은 삭제 파일도
    # 계속 나열한다. 파일을 지우는 작업 중에 가드가 죽지 않도록 건너뛴다.
    files = [
        root / rel_path
        for rel_path in tracked_paths
        if rel_path.endswith(SCANNED_EXTENSIONS)
        and "/migrations/" not in rel_path
        and (root / rel_path).is_file()
    ]
    assert files, "git ls-files 스캔 대상이 0개다 — 가드가 죽은 채로 통과하면 안 된다"
    return sorted(files)


def _span_to_lines(text, lines, start, end):
    """text 안 [start, end) 문자 오프셋이 걸치는 (1-based lineno, 원본 줄) 목록을 돌려준다."""
    start_lineno = text.count("\n", 0, start) + 1
    end_lineno = text.count("\n", 0, max(end - 1, start)) + 1
    return [
        (lineno, lines[lineno - 1])
        for lineno in range(start_lineno, end_lineno + 1)
        if 1 <= lineno <= len(lines)
    ]


def _python_comment_and_docstring_lines(path):
    source = path.read_text()
    lines = source.splitlines()
    results = []

    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT:
                results.append((token.start[0], token.string))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        pass

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return results

    docstring_owners = [tree]
    docstring_owners.extend(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    )
    for owner in docstring_owners:
        body = getattr(owner, "body", None)
        if not body:
            continue
        first = body[0]
        is_docstring = (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
        )
        if not is_docstring:
            continue
        start = first.lineno
        end = first.end_lineno or start
        for lineno in range(start, end + 1):
            if 1 <= lineno <= len(lines):
                results.append((lineno, lines[lineno - 1]))

    return results


def _css_comment_lines(path):
    text = path.read_text()
    lines = text.splitlines()
    results = []
    for match in re.finditer(r"/\*(.*?)\*/", text, re.DOTALL):
        results.extend(_span_to_lines(text, lines, match.start(1), match.end(1)))
    return results


def _js_comment_lines(path):
    text = path.read_text()
    lines = text.splitlines()
    results = []
    for match in re.finditer(r"/\*(.*?)\*/", text, re.DOTALL):
        results.extend(_span_to_lines(text, lines, match.start(1), match.end(1)))

    for lineno, line in enumerate(lines, start=1):
        for slash_match in re.finditer(r"//", line):
            before = line[: slash_match.start()]
            # 홀수 개의 따옴표가 앞서면 그 //는 문자열 리터럴 안이라고 본다.
            if before.count('"') % 2 == 1 or before.count("'") % 2 == 1 or before.count("`") % 2 == 1:
                continue
            results.append((lineno, line[slash_match.start() :]))
            break
    return results


def _html_comment_lines(path):
    text = path.read_text()
    lines = text.splitlines()
    results = []
    for match in re.finditer(r"<!--(.*?)-->", text, re.DOTALL):
        results.extend(_span_to_lines(text, lines, match.start(1), match.end(1)))
    for match in re.finditer(r"\{#(.*?)#\}", text, re.DOTALL):
        results.extend(_span_to_lines(text, lines, match.start(1), match.end(1)))
    for match in re.finditer(r"\{%\s*comment\s*%\}(.*?)\{%\s*endcomment\s*%\}", text, re.DOTALL):
        results.extend(_span_to_lines(text, lines, match.start(1), match.end(1)))
    return results


def _comment_lines_for(path):
    if path.suffix == ".py":
        return _python_comment_and_docstring_lines(path)
    if path.suffix == ".css":
        return _css_comment_lines(path)
    if path.suffix == ".js":
        return _js_comment_lines(path)
    if path.suffix == ".html":
        return _html_comment_lines(path)
    return []


def _violations(root):
    """위반 목록을 (프로덕션, 테스트) 두 묶음으로 나눠 돌려준다. 주석이 가장
    중요한 곳은 tests/가 아니라 비즈니스 로직이므로, 실패 메시지에서
    프로덕션 위반이 테스트 위반 수십 건에 묻히지 않게 항상 먼저 보여야
    한다 — 이 정렬을 "정리"해 하나의 목록으로 합치지 말 것."""
    production_violations = []
    test_violations = []
    for path in _iter_scanned_files(root):
        rel_path = path.relative_to(root)
        bucket = test_violations if rel_path.parts[0] == "tests" else production_violations
        for lineno, text in _comment_lines_for(path):
            if _is_violation_line(text):
                bucket.append(f"{rel_path}:{lineno}: {text.strip()}")
    return production_violations, test_violations


def test_추적_파일의_주석과_독스트링에_한글_없는_영어_산문이_없다():
    production_violations, test_violations = _violations(PROJECT_ROOT)

    assert not production_violations and not test_violations, (
        f"프로덕션 {len(production_violations)}건 / 테스트 {len(test_violations)}건\n"
        + "\n".join(production_violations + test_violations)
    )


@pytest.mark.parametrize(
    "text",
    [
        '{% include "core/partials/_archive_search.html" with q=q has_query=has_query %}',
        '<!ENTITY b "&a;&a;&a;&a;&a;">',
        "(effective_end := end_date if end_date is not None else start_date)",
        "- status row.updated_at — UserEventStatus.updated_at",
        'POST /staff/drafts/bulk-approve/ {"draft_ids":[...]} →',
        "visited                                            -> visited",
        "4px 11px",
        "~248px",
        "WCAG 2.4.3).",
    ],
    ids=[
        "django_include_with_속성",
        "xml_entity_반복",
        "왈러스_대입식",
        "필드_경로_표기",
        "curl_스타일_api_계약",
        "화살표_정렬표",
        "px_값_두개",
        "물결_px_값",
        "wcag_기준_번호",
    ],
)
def test_예외로_통과해야_하는_코드_표기_실물은_위반이_아니다(text):
    assert not _is_violation_line(text)


@pytest.mark.parametrize(
    "text",
    [
        "# No password requested: create_user(password=None) makes an",
        "Validation is delegated to events.image_validation.validate_uploaded_image",
        "# except-ok: isolated per-row so one failure cannot block the rest",
        "Deferred via transaction.on_commit so a rolled-back delete never loses a",
        "min-height: 44px added repo-wide (BIR IA-2 finding, applies to every",
    ],
    ids=[
        "식별자_호출_표기가_섞인_영어_산문",
        "긴_점_표기_경로가_섞인_영어_산문",
        "except_ok_마커_뒤_영어_사유",
        "코드_식별자와_영어_접속사가_섞인_산문",
        "css_속성_뒤에_붙은_영어_산문",
    ],
)
def test_오라클에서_가져온_실제_영어_산문_표본은_위반으로_잡힌다(text):
    assert _is_violation_line(text)


def test_한글_없는_영어_산문_두줄짜리_주석은_위반으로_잡힌다():
    assert _is_violation_line("This function is not obvious so we should explain it.")


def test_구조_구분선은_영어_단어를_포함해도_위반이_아니다():
    assert not _is_violation_line("── form fields that are required ──")


def test_todo_마커_뒤_영어_사유는_마커만_지워지고_위반으로_잡힌다():
    assert _is_violation_line("TODO(payment): this is where billing should attach later")


def test_todo_마커_뒤_한국어_사유는_위반이_아니다():
    assert not _is_violation_line("TODO(payment): 결제 연동 지점")
