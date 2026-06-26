import ast
from pathlib import Path

import pytest
from django.urls import Resolver404, resolve


PROJECT_ROOT = Path(__file__).resolve().parents[1]


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


@pytest.mark.parametrize("module_path", ["core/errors.py"])
def test_core_errors_do_not_import_domain_modules(module_path):
    imported_modules = _imported_modules(module_path)

    assert not {
        module
        for module in imported_modules
        if module in {"drafts", "events"} or module.startswith(("drafts.", "events."))
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
