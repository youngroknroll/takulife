"""Guard: public service-layer functions take keyword-only arguments.

events/services.py and archive/services.py already enforce this convention on
every public function (see their `*, ...` signatures). This guard protects
that convention from eroding as drafts/services.py, staff/services.py, and
core/promotion.py join it — a positional parameter on a public service
function is exactly the kind of drift this test exists to catch.

Private helpers (name starting with "_") are out of scope: they are an
internal implementation detail of their module, not a boundary other modules
call across, so this guard does not constrain their parameter style.
"""
import importlib
import inspect

import pytest


SERVICE_MODULES = [
    "events.services",
    "archive.services",
    "drafts.services",
    "staff.services",
    "core.promotion",
]


def _public_module_level_functions(module_name):
    module = importlib.import_module(module_name)
    return [
        (name, obj)
        for name, obj in vars(module).items()
        if inspect.isfunction(obj)
        and not name.startswith("_")
        and obj.__module__ == module_name
    ]


def _non_keyword_only_param_names(fn):
    return [
        name
        for name, param in inspect.signature(fn).parameters.items()
        if param.kind not in (inspect.Parameter.KEYWORD_ONLY, inspect.Parameter.VAR_KEYWORD)
    ]


@pytest.mark.parametrize("module_name", SERVICE_MODULES)
def test_public_service_functions_are_keyword_only(module_name):
    violations = {
        f"{module_name}.{name}": bad_params
        for name, fn in _public_module_level_functions(module_name)
        for bad_params in [_non_keyword_only_param_names(fn)]
        if bad_params
    }

    assert not violations, violations
