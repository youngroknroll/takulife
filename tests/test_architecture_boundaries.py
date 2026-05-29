import ast
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_draft_views_do_not_import_events_modules():
    tree = ast.parse((PROJECT_ROOT / "drafts" / "views.py").read_text())

    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert not {module for module in imported_modules if module == "events" or module.startswith("events.")}


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
    tree = ast.parse((PROJECT_ROOT / module_path).read_text())

    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert not {
        module
        for module in imported_modules
        if module in {"drafts", "events"} or module.startswith(("drafts.", "events."))
    }
