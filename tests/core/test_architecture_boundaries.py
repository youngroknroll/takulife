import ast
from pathlib import Path

import pytest
from django.urls import Resolver404, resolve


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _imported_modules(module_path):
    """Return all module names a source file imports (Import + ImportFrom)."""
    tree = ast.parse((PROJECT_ROOT / module_path).read_text())
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            modules.add(node.module)
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    return modules


def test_draft_views_do_not_import_events_modules():
    imported_modules = _imported_modules("drafts/views.py")

    assert not {module for module in imported_modules if module == "events" or module.startswith("events.")}


@pytest.mark.parametrize(
    "module_path",
    [
        "events/views.py",
        "events/serializers.py",
        "events/querysets.py",
        "events/services.py",
        "drafts/views.py",
        "drafts/services.py",
        "drafts/llm_extraction.py",
        "drafts/discovery.py",
        "drafts/management/commands/discover_drafts.py",
    ],
)
def test_active_non_archive_modules_do_not_import_archive_modules(module_path):
    imported_modules = _imported_modules(module_path)

    assert not {
        module
        for module in imported_modules
        if module == "archive" or module.startswith("archive.")
    }


@pytest.mark.parametrize("module_path", ["archive/models.py", "archive/serializers.py", "archive/services.py", "archive/views.py"])
def test_archive_modules_do_not_import_drafts_modules(module_path):
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
)
def test_domain_modules_do_not_import_staff_modules(module_path):
    """staff (presentation + audit infra) may depend on domain apps, never
    the reverse: events/drafts/archive must stay free of a `staff` import so
    domain business logic never leaks staff-only orchestration concerns."""
    imported_modules = _imported_modules(module_path)

    assert not {
        module
        for module in imported_modules
        if module == "staff" or module.startswith("staff.")
    }


def test_draft_discovery_does_not_import_events_modules():
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


def test_discover_drafts_command_does_not_import_events_modules():
    """discover_drafts orchestrates DraftSource -> EventDraft only, via
    create_draft_from_url (which itself owns the events.services boundary
    crossing) — the command has no reason to import events directly."""
    imported_modules = _imported_modules("drafts/management/commands/discover_drafts.py")

    assert not {
        module
        for module in imported_modules
        if module == "events" or module.startswith("events.")
    }


def test_draft_discovery_does_not_import_core_llm_modules():
    """LLM extraction is a separate, flag-gated concern (drafts/llm_extraction.py)
    — discovery.py's deterministic filters (prompt_plan.md §1-4) must not
    pull in core.llm."""
    imported_modules = _imported_modules("drafts/discovery.py")

    assert not {
        module
        for module in imported_modules
        if module == "core.llm" or module.startswith("core.llm.")
    }


def test_core_error_response_returns_detail_payload():
    from core.errors import error_response

    response = error_response("Not found.", 404)

    assert response.status_code == 404
    assert response.data == {"detail": "Not found."}


def test_core_field_error_response_returns_field_payload():
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
    ],
)
def test_core_errors_do_not_import_domain_modules(module_path):
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
)
def test_active_urlconf_does_not_resolve_deferred_archive_routes(path):
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
)
def test_active_urlconf_resolves_visit_record_routes(path):
    match = resolve(path)
    assert match.url_name in {
        "visit-record-list-create",
        "visit-record-detail",
        "visit-record-photo-create",
        "visit-record-photo-delete",
    }


@pytest.mark.parametrize("path", ["/api/user-event-statuses/", "/api/user-event-statuses/1/"])
def test_active_urlconf_resolves_user_event_status_routes(path):
    match = resolve(path)

    assert match.url_name in {"user-event-status-list-create", "user-event-status-detail"}


@pytest.mark.parametrize(
    "path",
    [
        "/api/event-drafts/1/approve/",
        "/api/event-drafts/1/reject/",
    ],
)
def test_old_draft_action_routes_do_not_resolve(path):
    """PR-2 sub-step D moved approve/reject to /staff/drafts/<id>/… with no
    redirect — the old drafts API paths must not resolve at all."""
    with pytest.raises(Resolver404):
        resolve(path)


def test_core_views_no_longer_imports_staff_permissions():
    """PR-2 sub-step D moved the 3 draft/home-category SSR views into
    staff.views — core.views must no longer depend on staff at all."""
    imported_modules = _imported_modules("core/views.py")

    assert not {
        module
        for module in imported_modules
        if module == "staff" or module.startswith("staff.")
    }


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


def test_api_and_view_test_files_do_not_import_service_or_query_layers():
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
