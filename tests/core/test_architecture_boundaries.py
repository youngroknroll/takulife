import ast
from pathlib import Path

import pytest
from django.urls import Resolver404, resolve


pytestmark = pytest.mark.contract

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _dynamic_import_target(call):
    """importlib.import_module(...) 또는 __import__(...) 호출이면 첫 인자 문자열을, 아니면 None을 돌려준다."""
    is_importlib_call = (
        isinstance(call.func, ast.Attribute)
        and call.func.attr == "import_module"
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "importlib"
    )
    is_builtin_import_call = isinstance(call.func, ast.Name) and call.func.id == "__import__"
    if not (is_importlib_call or is_builtin_import_call):
        return None
    if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
        return call.args[0].value
    return None


def _imported_modules(module_path):
    """Return all module names a source file imports (Import + ImportFrom + importlib.import_module/__import__ 호출)."""
    tree = ast.parse((PROJECT_ROOT / module_path).read_text())
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        # 동적 import도 정적 import처럼 다른 도메인을 불러올 수 있어 함께 본다.
        if isinstance(node, ast.Call):
            target = _dynamic_import_target(node)
            if target is not None:
                modules.add(target)
    return modules


def test_드래프트_뷰는_이벤트_모듈을_임포트하지_않는다():
    imported_modules = _imported_modules("drafts/views.py")

    assert not {module for module in imported_modules if module == "events" or module.startswith("events.")}


def test_동적_임포트로_다른_도메인을_불러오면_경계_스캐너가_탐지한다(tmp_path):
    fixture = tmp_path / "dynamic_import_fixture.py"
    fixture.write_text(
        "import importlib\n"
        'importlib.import_module("archive.models")\n'
    )

    # _imported_modules는 PROJECT_ROOT / module_path를 계산하는데, pathlib은
    # 우변이 절대 경로면 좌변을 버리므로 절대 경로 문자열을 그대로 넘기면 된다.
    imported_modules = _imported_modules(str(fixture))

    assert "archive.models" in imported_modules


def test_내장_import_함수로_다른_도메인을_불러오면_경계_스캐너가_탐지한다(tmp_path):
    fixture = tmp_path / "builtin_import_fixture.py"
    fixture.write_text('__import__("archive.models")\n')

    imported_modules = _imported_modules(str(fixture))

    assert "archive.models" in imported_modules


@pytest.mark.parametrize(
    "module_path",
    [
        "events/models.py",
        "events/views.py",
        "events/serializers.py",
        "events/querysets.py",
        "events/services.py",
        "events/queries.py",
        "drafts/models.py",
        "drafts/views.py",
        "drafts/services.py",
        "drafts/serializers.py",
        "drafts/queries.py",
        "drafts/llm_extraction.py",
        "drafts/discovery.py",
        "drafts/management/commands/discover_drafts.py",
    ],
    ids=[
        "이벤트_모델",
        "이벤트_뷰",
        "이벤트_시리얼라이저",
        "이벤트_쿼리셋",
        "이벤트_서비스",
        "이벤트_쿼리",
        "드래프트_모델",
        "드래프트_뷰",
        "드래프트_서비스",
        "드래프트_시리얼라이저",
        "드래프트_쿼리",
        "드래프트_LLM_추출",
        "드래프트_발견",
        "드래프트_수집_명령",
    ],
)
def test_활성_비아카이브_모듈은_아카이브_모듈을_임포트하지_않는다(module_path):
    imported_modules = _imported_modules(module_path)

    assert not {
        module
        for module in imported_modules
        if module == "archive" or module.startswith("archive.")
    }


@pytest.mark.parametrize(
    "module_path",
    ["archive/models.py", "archive/serializers.py", "archive/services.py", "archive/views.py"],
    ids=["아카이브_모델", "아카이브_시리얼라이저", "아카이브_서비스", "아카이브_뷰"],
)
def test_아카이브_모듈은_드래프트_모듈을_임포트하지_않는다(module_path):
    imported_modules = _imported_modules(module_path)

    assert not {
        module
        for module in imported_modules
        if module == "drafts" or module.startswith("drafts.")
    }


@pytest.mark.parametrize(
    "module_path",
    [
        "events/models.py",
        "events/views.py",
        "events/serializers.py",
        "events/querysets.py",
        "events/services.py",
        "drafts/models.py",
        "drafts/views.py",
        "drafts/services.py",
        "drafts/serializers.py",
        "drafts/llm_extraction.py",
        "drafts/discovery.py",
        "drafts/management/commands/discover_drafts.py",
        "archive/models.py",
        "archive/serializers.py",
        "archive/services.py",
        "archive/views.py",
    ],
    ids=[
        "이벤트_모델",
        "이벤트_뷰",
        "이벤트_시리얼라이저",
        "이벤트_쿼리셋",
        "이벤트_서비스",
        "드래프트_모델",
        "드래프트_뷰",
        "드래프트_서비스",
        "드래프트_시리얼라이저",
        "드래프트_LLM_추출",
        "드래프트_발견",
        "드래프트_수집_명령",
        "아카이브_모델",
        "아카이브_시리얼라이저",
        "아카이브_서비스",
        "아카이브_뷰",
    ],
)
def test_도메인_모듈은_스태프_모듈을_임포트하지_않는다(module_path):
    """staff (presentation + audit infra) may depend on domain apps, never
    the reverse: events/drafts/archive must stay free of a `staff` import so
    domain business logic never leaks staff-only orchestration concerns."""
    imported_modules = _imported_modules(module_path)

    assert not {
        module
        for module in imported_modules
        if module == "staff" or module.startswith("staff.")
    }


def test_드래프트_발견_모듈은_이벤트_모듈을_임포트하지_않는다():
    """discovery.py is a pure link-extraction module (prompt_plan.md §2-1) —
    unlike drafts/services.py, which legitimately imports events.services to
    orchestrate draft-to-event promotion, discovery.py has no reason to touch
    the events domain at all."""
    imported_modules = _imported_modules("drafts/discovery.py")

    assert not {
        module
        for module in imported_modules
        if module == "events" or module.startswith("events.")
    }


def test_드래프트_수집_명령은_이벤트_모듈을_임포트하지_않는다():
    """discover_drafts orchestrates DraftSource -> EventDraft only, via
    create_draft_from_url (which itself owns the events.services boundary
    crossing) — the command has no reason to import events directly."""
    imported_modules = _imported_modules("drafts/management/commands/discover_drafts.py")

    assert not {
        module
        for module in imported_modules
        if module == "events" or module.startswith("events.")
    }


def test_드래프트_발견_모듈은_core_llm_모듈을_임포트하지_않는다():
    """LLM extraction is a separate, flag-gated concern (drafts/llm_extraction.py)
    — discovery.py's deterministic filters (prompt_plan.md §1-4) must not
    pull in core.llm."""
    imported_modules = _imported_modules("drafts/discovery.py")

    assert not {
        module
        for module in imported_modules
        if module == "core.llm" or module.startswith("core.llm.")
    }


def test_에러_응답_헬퍼를_호출하면_detail_필드를_담은_응답을_반환한다():
    from core.errors import error_response

    response = error_response("Not found.", 404)

    assert response.status_code == 404
    assert response.data == {"detail": "Not found."}


def test_필드_에러_응답_헬퍼를_호출하면_필드명을_키로_하는_에러_페이로드를_반환한다():
    from core.errors import field_error_response

    response = field_error_response("official_url", "Duplicate")

    assert response.status_code == 400
    assert response.data == {"official_url": ["Duplicate"]}


@pytest.mark.parametrize(
    "module_path",
    [
        "core/errors.py",
        "core/llm/config.py",
        "core/llm/client.py",
        "core/llm/exceptions.py",
        "core/llm/__init__.py",
        "core/analytics.py",
    ],
    ids=["에러_모듈", "LLM_설정", "LLM_클라이언트", "LLM_예외", "LLM_초기화", "분석_모듈"],
)
def test_core_공용_모듈은_도메인_앱_모듈을_임포트하지_않는다(module_path):
    imported_modules = _imported_modules(module_path)

    forbidden_prefixes = ("drafts.", "events.", "archive.", "staff.", "accounts.")
    forbidden_names = {"drafts", "events", "archive", "staff", "accounts"}

    assert not {
        module
        for module in imported_modules
        if module in forbidden_names or module.startswith(forbidden_prefixes)
    }


@pytest.mark.parametrize(
    "path",
    [
        "/api/me/event-statuses/1/",
        "/api/me/visit-records/",
        "/api/me/visit-records/1/photos/",
        "/api/me/visit-records/1/photos/1/",
        "/api/visit-record-photos/",
        "/api/visit-record-photos/1/",
    ],
    ids=[
        "me_사용자_행사_상태_상세",
        "me_방문_기록_목록",
        "me_방문_기록_사진_목록",
        "me_방문_기록_사진_상세",
        "방문_기록_사진_목록",
        "방문_기록_사진_상세",
    ],
)
def test_활성_urlconf는_보류된_아카이브_라우트를_해석하지_않는다(path):
    with pytest.raises(Resolver404):
        resolve(path)


@pytest.mark.parametrize(
    "path",
    [
        "/api/visit-records/",
        "/api/visit-records/1/",
        "/api/visit-records/1/photos/",
        "/api/visit-records/1/photos/1/",
    ],
    ids=["목록_생성", "상세", "사진_생성", "사진_삭제"],
)
def test_활성_urlconf는_방문_기록_라우트를_해석한다(path):
    match = resolve(path)
    assert match.url_name in {
        "visit-record-list-create",
        "visit-record-detail",
        "visit-record-photo-create",
        "visit-record-photo-delete",
    }


@pytest.mark.parametrize(
    "path",
    ["/api/user-event-statuses/", "/api/user-event-statuses/1/"],
    ids=["목록_생성", "상세"],
)
def test_활성_urlconf는_사용자_행사_상태_라우트를_해석한다(path):
    match = resolve(path)

    assert match.url_name in {"user-event-status-list-create", "user-event-status-detail"}


@pytest.mark.parametrize(
    "path",
    [
        "/api/event-drafts/1/approve/",
        "/api/event-drafts/1/reject/",
    ],
    ids=["승인", "반려"],
)
def test_구_드래프트_액션_라우트는_더이상_해석되지_않는다(path):
    """PR-2 sub-step D moved approve/reject to /staff/drafts/<id>/… with no
    redirect — the old drafts API paths must not resolve at all."""
    with pytest.raises(Resolver404):
        resolve(path)


def test_core_뷰는_더이상_스태프_모듈을_임포트하지_않는다():
    """PR-2 sub-step D moved the 3 draft/home-category SSR views into
    staff.views — core.views must no longer depend on staff at all. core.views
    is now a package (core/views/), so every module file under it is scanned."""
    view_module_paths = sorted((PROJECT_ROOT / "core" / "views").rglob("*.py"))
    assert view_module_paths, "core/views 아래 스캔할 .py 파일이 없다"

    for module_path in view_module_paths:
        relative_path = module_path.relative_to(PROJECT_ROOT)
        imported_modules = _imported_modules(str(relative_path))

        violating_modules = {
            module
            for module in imported_modules
            if module == "staff" or module.startswith("staff.")
        }
        assert not violating_modules, f"{relative_path}가 staff 모듈을 임포트한다: {violating_modules}"


# ---------------------------------------------------------------------------
# Test-layer purity: "test file name = layer under test" contract
#
# The test-suite refactor (PR-9/PR-10) separated tests into dedicated files
# per layer (HTTP API, SSR view, service, query) so a file's name tells the
# reader exactly which boundary it exercises. This guard protects that
# contract from eroding: an *_api.py / *_view(s).py test file that imports a
# services/queries module is a sign a test reached past the HTTP/SSR
# boundary to arrange state directly — that test belongs in the matching
# *_services.py / *_queries.py file instead (see
# tests/archive/test_archive_services.py, tests/archive/test_archive_queries.py).
# ---------------------------------------------------------------------------

API_OR_VIEW_TEST_GLOBS = ("test_*_api.py", "test_*_view.py", "test_*_views.py")
_DOMAIN_APPS_WITH_SERVICE_QUERY_LAYERS = ("archive", "drafts", "events", "staff")
_CLIENT_FAMILY_FIXTURE_NAMES = ("client", "admin_client", "user_client", "staff_client")

# (file, module) -> the exact names this guard permits importing from that
# module. Anything imported that is not in this set fails the guard — this
# is a per-name allow-list, not a per-file exemption, so widening what a
# file imports from services/queries (even within an already-allowed module)
# requires touching this table.
ALLOWED_SERVICE_OR_QUERY_IMPORTS_IN_API_OR_VIEW_TESTS = {
    # Imports only the DraftCreation*Error exception classes, to monkeypatch
    # draft_views.create_draft_from_url so it raises them — this exercises
    # the API's error-to-status-code mapping contract, never calling the
    # service function to arrange data. (The actual monkeypatch targets,
    # e.g. 'drafts.services.fetch_html', are string paths passed to
    # monkeypatch.setattr, which this AST check cannot see and which are
    # not imports anyway.)
    ("tests/drafts/test_drafts_api.py", "drafts.services"): frozenset(
        {
            "DraftCreationEmptyExtractionError",
            "DraftCreationResponseTooLargeError",
            "DraftCreationUnsupportedContentError",
        }
    ),
    # Imports only the STAFF_EVENT_LISTING_PAGE_SIZE constant, to compute how
    # many events to seed for a pagination test — no query function is
    # called.
    ("tests/staff/test_staff_events_views.py", "events.queries"): frozenset(
        {"STAFF_EVENT_LISTING_PAGE_SIZE"}
    ),
    # Imports only the DRAFT_LISTING_PAGE_SIZE constant, to compute how many
    # drafts to seed for a pagination test — no query function is called.
    ("tests/staff/test_staff_draft_views.py", "drafts.queries"): frozenset(
        {"DRAFT_LISTING_PAGE_SIZE"}
    ),
    # Imports only the ARCHIVE_COLLECTION_PAGE_SIZE constant, to compute how
    # many collection items to seed for a pagination test — no query
    # function is called.
    ("tests/archive/test_archive_collection_view.py", "archive.queries"): frozenset(
        {"ARCHIVE_COLLECTION_PAGE_SIZE"}
    ),
    # Imports only the MAX_PHOTOS_PER_RECORD constant, to compute how many
    # untokened photos to seed up to the cap for the photo-upload idempotency
    # tests — no service function is called.
    ("tests/archive/test_visit_records_api.py", "archive.services"): frozenset(
        {"MAX_PHOTOS_PER_RECORD"}
    ),
}

# Sentinel used when a test file imports the whole services/queries module
# object (`import <app>.services`, or `from <app> import services`) rather
# than specific names — there is nothing to whitelist by name in that case,
# so any such import is always a violation unless "*" itself is allow-listed.
_WHOLE_MODULE_IMPORT = "*"


def _imported_names_by_service_or_query_module(module_path, apps):
    """Return {"<app>.services" or "<app>.queries": {imported names}} for a
    test file, resolving all three import spellings (`import <app>.services`,
    `from <app>.services import X`, `from <app> import services`) into the
    same module key. A bare module import (no specific names) is recorded
    under the sentinel name "*" (see _WHOLE_MODULE_IMPORT)."""
    tree = ast.parse((PROJECT_ROOT / module_path).read_text())
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                for app in apps:
                    if alias.name == f"{app}.services" or alias.name == f"{app}.queries":
                        found.setdefault(alias.name, set()).add(_WHOLE_MODULE_IMPORT)
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            for app in apps:
                if node.module == f"{app}.services" or node.module == f"{app}.queries":
                    for alias in node.names:
                        found.setdefault(node.module, set()).add(alias.name)
                elif node.module == app:
                    for alias in node.names:
                        if alias.name in ("services", "queries"):
                            found.setdefault(f"{app}.{alias.name}", set()).add(_WHOLE_MODULE_IMPORT)
    return found


def _has_client_family_fixture(path):
    """True if any test function in the file declares a client/admin_client/
    user_client/staff_client parameter — a structural AST fact (the argument
    name in a `def test_...(...)` signature), not a variable-name guess at
    call sites."""
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            if any(arg.arg in _CLIENT_FAMILY_FIXTURE_NAMES for arg in node.args.args):
                return True
    return False


def test_api_view_계층_테스트_파일은_서비스_쿼리_계층을_임포트하지_않는다():
    """API/view-layer test files must exercise only the HTTP/SSR boundary.
    A test that needs to reach into a services/queries module directly
    belongs in a dedicated *_services.py / *_queries.py file instead — that
    is the "test file name = layer under test" contract this refactor
    established.

    In scope by two independent signals: the filename pattern
    (*_api.py / *_view(s).py) and, more broadly, any test file that
    declares a client-family fixture parameter (it exercises HTTP/SSR
    regardless of what its filename says). Legitimate narrow exceptions are
    tracked by exact imported name in
    ALLOWED_SERVICE_OR_QUERY_IMPORTS_IN_API_OR_VIEW_TESTS, with the reason
    as a comment above each entry.
    """
    tests_dir = PROJECT_ROOT / "tests"

    files_by_glob = set()
    for pattern in API_OR_VIEW_TEST_GLOBS:
        files_by_glob.update(tests_dir.glob(f"**/{pattern}"))

    files_by_fixture = {
        path for path in tests_dir.glob("**/test_*.py") if _has_client_family_fixture(path)
    }

    test_files = files_by_glob | files_by_fixture
    assert test_files, "layer-purity guard matched 0 files — glob broken or tests moved"

    violations = []
    for path in sorted(test_files):
        rel_path = path.relative_to(PROJECT_ROOT).as_posix()
        matched_by = []
        if path in files_by_glob:
            matched_by.append("filename")
        if path in files_by_fixture:
            matched_by.append("client-fixture")

        imported_names_by_module = _imported_names_by_service_or_query_module(
            rel_path, _DOMAIN_APPS_WITH_SERVICE_QUERY_LAYERS
        )
        for module, names in imported_names_by_module.items():
            allowed = ALLOWED_SERVICE_OR_QUERY_IMPORTS_IN_API_OR_VIEW_TESTS.get(
                (rel_path, module), frozenset()
            )
            disallowed = names - allowed
            if disallowed:
                violations.append(
                    f"{rel_path} (matched by {'+'.join(matched_by)}) imports "
                    f"{', '.join(sorted(disallowed))} from {module}"
                )

    assert not violations, "\n".join(violations)
