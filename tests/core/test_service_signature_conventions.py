"""가드: 공개 서비스 계층 함수는 키워드 전용 인자만 받는다.

events/services.py와 archive/services.py는 이미 모든 공개 함수에 이 관례를
지킨다(`*, ...` 시그니처 참고). drafts/services.py, staff/services.py,
web/promotion.py, core/analytics.py가 합류하면서 이 관례가 무너지지 않도록
지키는 가드다 — 공개 서비스 함수의 위치 인자가 바로 이 테스트가 잡으려는
이탈이다.

비공개 헬퍼(이름이 "_"로 시작)는 대상 밖이다 — 다른 모듈이 넘어 다니는
경계가 아니라 해당 모듈 내부 구현 세부이므로 이 가드가 인자 스타일을
강제하지 않는다.

accounts.services는 SERVICE_MODULES에서 일부러 뺐다 — 공개 함수의 모든
호출자가 accounts 앱 내부에 있어 이 가드가 지키는 도메인 간 경계를 형성하지
않으므로, 위치 인자를 써도 이 관례 위반이 아니다.
"""
import importlib
import inspect

import pytest


SERVICE_MODULES = [
    "events.services",
    "archive.services",
    "drafts.services",
    "drafts.discovery_runs",
    "staff.services",
    "web.promotion",
    "core.analytics",
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


pytestmark = pytest.mark.contract


@pytest.mark.parametrize(
    "module_name",
    SERVICE_MODULES,
    ids=[
        "events_서비스",
        "archive_서비스",
        "drafts_서비스",
        "drafts_discovery_runs",
        "staff_서비스",
        "web_promotion",
        "core_analytics",
    ],
)
def test_공개_서비스_함수는_키워드_전용_인자만_받는다(module_name):
    violations = {
        f"{module_name}.{name}": bad_params
        for name, fn in _public_module_level_functions(module_name)
        for bad_params in [_non_keyword_only_param_names(fn)]
        if bad_params
    }

    assert not violations, violations
