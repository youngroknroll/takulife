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


def _parse_imported_module_names(source_path):
    """정적 Import/ImportFrom과 동적 importlib.import_module/__import__ 호출에서
    임포트된 모듈명을 모은다. 상대 임포트(level>0)는 건너뛴다 — 이 저장소의 앱은
    전부 최상위 패키지라 상대 임포트로는 앱 경계를 넘을 수 없으므로, 건너뛰어도
    탐지력 손실은 0이고 core/views·staff/views의 `from .archive import ...`
    같은 오탐만 사라진다(.docs/BE/boundary-guard-glob-plan.md 승인 범위 3).
    `_imported_modules`와 `_forbidden_imports_in_file`이 공유하는 단일 파서다."""
    tree = ast.parse(source_path.read_text())
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module is not None:
            if node.level:
                continue
            modules.add(node.module)
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        # 동적 import도 정적 import처럼 다른 도메인을 불러올 수 있어 함께 본다.
        if isinstance(node, ast.Call):
            target = _dynamic_import_target(node)
            if target is not None:
                modules.add(target)
    return modules


def _imported_modules(module_path):
    """Return all module names a source file imports — PROJECT_ROOT 상대경로
    문자열을 받는 얇은 래퍼. 실제 파싱은 _parse_imported_module_names가 한다."""
    return _parse_imported_module_names(PROJECT_ROOT / module_path)


# ---------------------------------------------------------------------------
# 파일시스템 유도 스캔: 손유지 파라미터 목록 대신 root 아래를 직접 순회한다.
# root를 주입받아 실제 PROJECT_ROOT와 tmp_path 합성 트리 양쪽에 쓸 수 있다
# (.docs/BE/boundary-guard-glob-plan.md 승인 범위 1).
# ---------------------------------------------------------------------------


def _domain_source_files(root, app_names):
    """root 아래 app_names 각각의 *.py를 재귀 순회한다. migrations/는 데이터
    마이그레이션이 apps.get_model() historical API를 써서 앱 임포트 경로를
    타지 않으므로 제외한다. 발견 결과가 0개면(오탈자 난 앱 이름 포함) 공허하게
    통과하지 않고 즉시 실패한다."""
    files = []
    for app_name in app_names:
        app_dir = root / app_name
        for path in sorted(app_dir.rglob("*.py")):
            if "migrations" in path.relative_to(app_dir).parts:
                continue
            files.append(path)
    assert files, f"{app_names} 아래 스캔할 .py 파일이 없다 (root={root})"
    return files


def _forbidden_imports_in_file(path, forbidden_apps):
    """path가 forbidden_apps 중 하나를 임포트하면 그 모듈명 집합을 돌려준다."""
    modules = _parse_imported_module_names(path)
    return {
        module
        for module in modules
        if any(module == app or module.startswith(f"{app}.") for app in forbidden_apps)
    }


# ---------------------------------------------------------------------------
# core 공용 모듈 도메인 임포트 가드 — 기본 거부(default-deny) + 허용 목록.
# 손유지 목록이 아니라 core/**/*.py 전부를 스캔하고, 정당한 예외 두 건만
# 허용 목록에 근거와 함께 등록한다(.docs/BE/boundary-guard-glob-plan.md 승인
# 범위 4). 심볼 단위가 아니라 모듈/디렉터리 단위다 — 471행 아래
# ALLOWED_SERVICE_OR_QUERY_IMPORTS_IN_API_OR_VIEW_TESTS는 테스트 계층 순수성을
# 지키는 다른 가드의 표이며, 그 심볼 단위 입도를 여기로 가져오면 core/views가
# 새 함수를 하나 쓸 때마다 표를 고쳐야 해서 손유지 목록으로 회귀한다.
# ---------------------------------------------------------------------------


def _is_core_domain_import_allowlisted(path, root):
    """path(core/ 하위 실제 파일)가 도메인 임포트 허용 목록에 해당하면 True.
    root를 인자로 받아야 한다 — PROJECT_ROOT를 하드코딩하면 합성 tmp_path
    트리에서 relative_to가 ValueError를 던지거나 항상 허용/거부로 고정된다.
    경로 비교는 세그먼트 완전 일치다 — `"views" in str(path)` 같은 부분
    문자열 비교는 core/promotion_views.py(이름이 promotion으로 시작하고
    views를 포함)나 core/views_extra.py(디렉터리 밖, 이름만 유사) 같은
    실재하는 파일을 조용히 새게 한다."""
    relative_parts = path.relative_to(root / "core").parts
    if relative_parts[:1] == ("views",):
        # core/views/ 디렉터리 전체 — 프레젠테이션 합성 계층. 쓰기 호출 0건
        # (유일한 `.update(`는 딕셔너리 `context.update(...)`), 쓰기는 기존
        # DRF API로 간다. 패키지 전체 예외이며, 개별 파일이 실제로 도메인을
        # 임포트하는지는 별개다 — system.py/__init__.py처럼 도메인 임포트가
        # 0건인 파일도 이 예외에 포함된다.
        return True
    if relative_parts == ("promotion.py",):
        # 유일한 교차 도메인 쓰기 오케스트레이터 — transaction.atomic()과
        # select_for_update()를 소유해 core/views/와 성격이 달라 별도 파일
        # 엔트리로 등록한다(디렉터리로 묶지 않는다).
        return True
    return False


def _local_domain_apps(root):
    """core를 제외한 이 프로젝트 소유 앱 이름 집합을 Django 앱 레지스트리에서
    파생시킨다 — 손으로 쓴 리터럴이 사라지면 새 로컬 앱이 INSTALLED_APPS에
    추가되는 순간 자동으로 금지 집합에 들어온다. 함수 안에서만
    django.apps.apps를 호출해 settings 구성 이전 import-time 호출을 피한다.

    로컬 앱 판정은 `AppConfig.path`의 부모 디렉터리가 root와 같은지로 한다 —
    단순히 `Path(path).is_relative_to(root)`만 쓰면 이 저장소의 `.venv`가
    프로젝트 루트 바로 아래에 있어(`uv`가 인repo venv를 만듦) rest_framework,
    axes, allauth 같은 서드파티까지 "root 아래"로 오탐된다. 로컬 앱은 항상
    root의 직계 자식 디렉터리(`archive/`, `events/` 등)이므로 parent 비교가
    실제 경계다.
    """
    from django.apps import apps as django_apps

    local_app_names = {
        config.name
        for config in django_apps.get_app_configs()
        if Path(config.path).resolve().parent == root
    }
    forbidden = local_app_names - {"core"}
    assert forbidden, f"파생된 금지 앱 집합이 비어 있다 (root={root}) — 앱 레지스트리 스캔이 잘못됐다"
    return forbidden


CORE_FORBIDDEN_DOMAIN_APPS = _local_domain_apps(PROJECT_ROOT)


def test_금지_앱_집합은_로컬_도메인_앱을_담고_서드파티와_core_자신은_뺀다():
    forbidden = _local_domain_apps(PROJECT_ROOT)

    assert "archive" in forbidden
    assert "rest_framework" not in forbidden
    assert "core" not in forbidden


def test_금지_앱_파생_대상이_없는_root는_공허하게_통과하지_않고_실패한다(tmp_path):
    with pytest.raises(AssertionError):
        _local_domain_apps(tmp_path)


def test_core_promotion_모듈의_실제_도메인_임포트는_허용_목록으로_통과한다():
    path = PROJECT_ROOT / "core" / "promotion.py"

    forbidden = _forbidden_imports_in_file(path, CORE_FORBIDDEN_DOMAIN_APPS)
    assert forbidden, "promotion.py가 도메인 모듈을 임포트하지 않는다 — 이 시나리오의 전제가 깨졌다"
    assert _is_core_domain_import_allowlisted(path, PROJECT_ROOT)


def test_core_views_패키지_전체의_실제_도메인_임포트는_허용_목록으로_통과한다():
    # system.py/__init__.py는 일부러 뺀다 — 도메인 임포트가 0건이라 "허용
    # 목록 덕분에 통과"인지 "애초에 안 잡히는 것"인지 구분되지 않는다.
    view_module_names = ("_helpers.py", "account.py", "activity.py", "archive.py", "collection.py", "events.py")
    view_module_paths = [PROJECT_ROOT / "core" / "views" / name for name in view_module_names]

    for path in view_module_paths:
        forbidden = _forbidden_imports_in_file(path, CORE_FORBIDDEN_DOMAIN_APPS)
        assert forbidden, f"{path.name}가 도메인 모듈을 임포트하지 않는다 — 이 시나리오의 전제가 깨졌다"
        assert _is_core_domain_import_allowlisted(path, PROJECT_ROOT), path


def test_core_views_디렉터리에_새로_생기는_파일도_등록_없이_허용된다(tmp_path):
    (tmp_path / "core" / "views").mkdir(parents=True)
    new_module = tmp_path / "core" / "views" / "new_module.py"
    new_module.write_text("import archive.models\n")

    assert _is_core_domain_import_allowlisted(new_module, tmp_path)


def test_core_views_디렉터리_밖의_이름만_유사한_파일은_허용되지_않는다(tmp_path):
    (tmp_path / "core" / "views").mkdir(parents=True)
    lookalike = tmp_path / "core" / "views_extra.py"
    lookalike.write_text("import archive.models\n")
    control = tmp_path / "core" / "views" / "actual.py"
    control.write_text("import archive.models\n")

    assert not _is_core_domain_import_allowlisted(lookalike, tmp_path)
    assert _is_core_domain_import_allowlisted(control, tmp_path)


def test_promotion_py와_파일명_접두만_같은_새_파일은_허용되지_않는다(tmp_path):
    (tmp_path / "core").mkdir()
    lookalike = tmp_path / "core" / "promotion_extra.py"
    lookalike.write_text("import archive.models\n")
    control = tmp_path / "core" / "promotion.py"
    control.write_text("import archive.models\n")

    assert not _is_core_domain_import_allowlisted(lookalike, tmp_path)
    assert _is_core_domain_import_allowlisted(control, tmp_path)


def test_core_공용_모듈은_허용_목록_밖에서_도메인_앱_모듈을_임포트하지_않는다():
    files = _domain_source_files(PROJECT_ROOT, ["core"])

    violations = {
        path.relative_to(PROJECT_ROOT): forbidden
        for path in files
        if not _is_core_domain_import_allowlisted(path, PROJECT_ROOT)
        and (forbidden := _forbidden_imports_in_file(path, CORE_FORBIDDEN_DOMAIN_APPS))
    }

    assert not violations, violations


def test_스캔_대상이_없는_root는_공허하게_통과하지_않고_실패한다(tmp_path):
    with pytest.raises(AssertionError):
        _domain_source_files(tmp_path, ["events"])


def test_오탈자_난_앱_이름도_공허하게_통과하지_않고_실패한다(tmp_path):
    (tmp_path / "events").mkdir()
    (tmp_path / "events" / "models.py").write_text("")

    with pytest.raises(AssertionError):
        _domain_source_files(tmp_path, ["evnets"])


def test_손유지_목록에_없는_새_파일의_금지_임포트도_탐지한다(tmp_path):
    (tmp_path / "events").mkdir()
    (tmp_path / "archive").mkdir()
    # poison.py는 어떤 가드의 하드코딩 목록에도 등장한 적 없는 파일명이다 —
    # root 주입 없이는 이 사각지대를 애초에 재현할 수 없었다.
    (tmp_path / "events" / "poison.py").write_text("import archive.models\n")
    (tmp_path / "archive" / "models.py").write_text("")

    files = _domain_source_files(tmp_path, ["events", "archive"])
    violations = {
        path: mods
        for path in files
        if (mods := _forbidden_imports_in_file(path, {"archive"}))
    }

    assert any(path.name == "poison.py" for path in violations), violations


def test_같은_이름의_로컬_서브모듈을_상대_임포트하면_위반으로_잡히지_않는다(tmp_path):
    """core/views/__init__.py의 `from .archive import (...)` 형태를 재현한다.
    이 저장소의 앱은 전부 최상위 패키지라 상대 임포트(level>0)로는 애초에
    앱 경계를 넘을 수 없다 — archive라는 이름의 로컬 서브모듈(core/views/archive.py)을
    상대 경로로 부르는 것과, archive 앱을 절대 경로로 부르는 것은 이름은
    같아도 다른 대상이므로 전자는 오탐이다. 이 방어선은 core 가드를 손유지
    목록에서 글롭으로 전환하는 후속 작업의 선행 조건이다."""
    (tmp_path / "core" / "views").mkdir(parents=True)
    (tmp_path / "core" / "views" / "__init__.py").write_text(
        "from .archive import archive\n"
    )
    (tmp_path / "core" / "views" / "archive.py").write_text("")
    (tmp_path / "archive").mkdir()
    (tmp_path / "archive" / "models.py").write_text("")

    files = _domain_source_files(tmp_path, ["core", "archive"])
    violations = {
        path: mods
        for path in files
        if (mods := _forbidden_imports_in_file(path, {"archive"}))
    }

    assert not violations, violations


def test_같은_이름의_절대_임포트는_상대_임포트_스킵과_무관하게_여전히_잡힌다(tmp_path):
    """앞선 오탐 방지 테스트가 스킵 로직을 통째로 넓히는 방향(모든 ImportFrom
    스킵)으로 퇴화해도 통과해버리지 않도록 대조하는 테스트다 — 같은 archive라는
    이름이라도 level=0인 절대 임포트는 실제로 archive 앱 경계를 넘으므로
    여전히 위반으로 탐지되어야 한다."""
    (tmp_path / "core" / "views").mkdir(parents=True)
    (tmp_path / "core" / "views" / "__init__.py").write_text(
        "from archive import archive\n"
    )
    (tmp_path / "archive").mkdir()
    (tmp_path / "archive" / "models.py").write_text("")

    files = _domain_source_files(tmp_path, ["core", "archive"])
    violations = {
        path: mods
        for path in files
        if (mods := _forbidden_imports_in_file(path, {"archive"}))
    }

    assert any(path.name == "__init__.py" for path in violations), violations


def test_금지_임포트가_없는_새_파일은_위반으로_보고되지_않는다(tmp_path):
    (tmp_path / "events").mkdir()
    (tmp_path / "archive").mkdir()
    (tmp_path / "events" / "clean.py").write_text("import os\n")
    (tmp_path / "archive" / "models.py").write_text("")

    files = _domain_source_files(tmp_path, ["events", "archive"])
    violations = {
        path: mods
        for path in files
        if (mods := _forbidden_imports_in_file(path, {"archive"}))
    }

    assert not violations, violations


def test_실제_저장소_스캔_대상에_이벤트_모델이_포함된다():
    """글롭이 나중에 *.py에서 views.py로 좁혀지면 여기서 시끄럽게 깨진다 —
    models.py는 뷰가 아니므로."""
    files = _domain_source_files(PROJECT_ROOT, ["events"])

    assert any(path.relative_to(PROJECT_ROOT) == Path("events/models.py") for path in files)


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


def test_활성_비아카이브_모듈은_아카이브_모듈을_임포트하지_않는다():
    files = _domain_source_files(PROJECT_ROOT, ["events", "drafts"])

    violations = {
        path.relative_to(PROJECT_ROOT): forbidden
        for path in files
        if (forbidden := _forbidden_imports_in_file(path, {"archive"}))
    }

    assert not violations, violations


def test_accounts_모듈은_아카이브_모듈을_임포트하지_않는다():
    """B5(account-settings-editorial 계획서)는 탈퇴 화면의 archive 카운트
    합성을 core/views/account.py에만 두고 accounts는 archive를 임포트하지
    않는 것을 전제로 한다 — 기존 스캔 대상이 ["events", "drafts"]뿐이라
    accounts가 목록 밖이었던 사각지대(AS-13)를 신설한다."""
    files = _domain_source_files(PROJECT_ROOT, ["accounts"])

    violations = {
        path.relative_to(PROJECT_ROOT): forbidden
        for path in files
        if (forbidden := _forbidden_imports_in_file(path, {"archive"}))
    }

    assert not violations, violations


def test_아카이브_모듈은_드래프트_모듈을_임포트하지_않는다():
    files = _domain_source_files(PROJECT_ROOT, ["archive"])

    violations = {
        path.relative_to(PROJECT_ROOT): forbidden
        for path in files
        if (forbidden := _forbidden_imports_in_file(path, {"drafts"}))
    }

    assert not violations, violations


def test_이벤트_모듈은_드래프트_모듈을_임포트하지_않는다():
    """승인된 의존 방향은 `drafts/services.py` -> `events.services`
    단방향뿐이다(AGENTS.md) — 정당한 그 반대 방향과 혼동하지 말 것. 이
    테스트가 잡는 것은 events가 drafts를 끌어오는, 근거 없는 역방향이다."""
    files = _domain_source_files(PROJECT_ROOT, ["events"])

    violations = {
        path.relative_to(PROJECT_ROOT): forbidden
        for path in files
        if (forbidden := _forbidden_imports_in_file(path, {"drafts"}))
    }

    assert not violations, violations


def test_도메인_모듈은_스태프_모듈을_임포트하지_않는다():
    """staff(화면+감사 인프라)는 도메인 앱에 의존할 수 있어도 반대는 금지다 —
    events/drafts/archive가 staff를 임포트하면 도메인 규칙에 화면 전용
    로직이 새어 들어간다."""
    files = _domain_source_files(PROJECT_ROOT, ["events", "drafts", "archive"])

    violations = {
        path.relative_to(PROJECT_ROOT): forbidden
        for path in files
        if (forbidden := _forbidden_imports_in_file(path, {"staff"}))
    }

    assert not violations, violations


def test_드래프트_발견_모듈은_이벤트_모듈을_임포트하지_않는다():
    """discovery.py는 링크 추출만 하는 순수 모듈이다 — 드래프트 승격을 위해
    events.services를 정당하게 임포트하는 drafts/services.py와 달리, 여기는
    events 도메인을 건드릴 이유가 없다."""
    imported_modules = _imported_modules("drafts/discovery.py")

    assert not {
        module
        for module in imported_modules
        if module == "events" or module.startswith("events.")
    }


def test_드래프트_수집_명령은_이벤트_모듈을_임포트하지_않는다():
    """discover_drafts는 create_draft_from_url을 통해서만 DraftSource를
    EventDraft로 이어준다(경계를 넘는 책임은 그 함수가 진다) — 이 명령이
    events를 직접 임포트할 이유는 없다."""
    imported_modules = _imported_modules("drafts/management/commands/discover_drafts.py")

    assert not {
        module
        for module in imported_modules
        if module == "events" or module.startswith("events.")
    }


def test_드래프트_발견_모듈은_core_llm_모듈을_임포트하지_않는다():
    """LLM 추출은 플래그로 켜고 끄는 별도 관심사(drafts/llm_extraction.py)다
    — discovery.py의 결정적 필터링 로직은 core.llm을 끌어오면 안 된다."""
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
    """승인/반려는 /staff/drafts/<id>/… 로 옮겨갔고 리다이렉트는 없다 — 옛
    드래프트 API 경로는 전혀 해석되지 않아야 한다."""
    with pytest.raises(Resolver404):
        resolve(path)


def test_core_뷰는_더이상_스태프_모듈을_임포트하지_않는다():
    """드래프트·홈카테고리 SSR 뷰 3개가 staff.views로 옮겨가 core.views는
    더이상 staff에 의존하면 안 된다. core.views가 패키지(core/views/)이므로
    그 아래 모든 모듈 파일을 스캔한다."""
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
# 테스트 계층 순수성 — "파일명 = 검증 계층" 규약.
# 테스트는 계층(HTTP API, SSR 뷰, 서비스, 쿼리)별로 전용 파일에 나뉘어 있어
# 파일명만 보면 어떤 경계를 검증하는지 알 수 있다. 이 가드는 그 규약이
# 무너지지 않도록 지킨다 — *_api.py / *_view(s).py 테스트가 services/queries
# 모듈을 임포트한다면 HTTP/SSR 경계를 넘어 직접 상태를 조립했다는 신호이며,
# 그런 테스트는 대응하는 *_services.py / *_queries.py 파일로 옮겨야 한다
# (tests/archive/test_archive_services.py, tests/archive/test_archive_queries.py 참고).
# ---------------------------------------------------------------------------

API_OR_VIEW_TEST_GLOBS = ("test_*_api.py", "test_*_view.py", "test_*_views.py")
_DOMAIN_APPS_WITH_SERVICE_QUERY_LAYERS = ("archive", "drafts", "events", "staff")
_CLIENT_FAMILY_FIXTURE_NAMES = ("client", "admin_client", "user_client", "staff_client")

# (파일, 모듈) -> 그 모듈에서 임포트를 허용하는 정확한 이름 집합. 여기 없는
# 이름을 임포트하면 가드가 실패한다 — 파일 단위 예외가 아니라 이름 단위
# 허용 목록이라, 이미 허용된 모듈 안에서도 새 이름을 쓰려면 이 표를 고쳐야
# 한다.
ALLOWED_SERVICE_OR_QUERY_IMPORTS_IN_API_OR_VIEW_TESTS = {
    # DraftCreation*Error 예외 클래스만 임포트해 draft_views.create_draft_from_url이
    # 그 예외를 던지도록 monkeypatch한다 — 서비스 함수를 호출해 데이터를
    # 조립하는 게 아니라 API의 에러→상태코드 매핑만 검증한다. (실제
    # monkeypatch 대상인 'drafts.services.fetch_html' 같은 문자열 경로는
    # monkeypatch.setattr에 넘기는 값이라 이 AST 검사로는 보이지 않고,
    # 애초에 임포트도 아니다.)
    ("tests/drafts/test_drafts_api.py", "drafts.services"): frozenset(
        {
            "DraftCreationEmptyExtractionError",
            "DraftCreationResponseTooLargeError",
            "DraftCreationUnsupportedContentError",
        }
    ),
    # STAFF_EVENT_LISTING_PAGE_SIZE 상수만 임포트해 페이지네이션 테스트용
    # 행사 시드 개수를 계산한다 — 쿼리 함수는 호출하지 않는다.
    ("tests/staff/test_staff_events_views.py", "events.queries"): frozenset(
        {"STAFF_EVENT_LISTING_PAGE_SIZE"}
    ),
    # DRAFT_LISTING_PAGE_SIZE 상수만 임포트해 페이지네이션 테스트용 드래프트
    # 시드 개수를 계산한다 — 쿼리 함수는 호출하지 않는다.
    ("tests/staff/test_staff_draft_views.py", "drafts.queries"): frozenset(
        {"DRAFT_LISTING_PAGE_SIZE"}
    ),
    # ARCHIVE_COLLECTION_PAGE_SIZE 상수만 임포트해 페이지네이션 테스트용
    # 컬렉션 아이템 시드 개수를 계산한다 — 쿼리 함수는 호출하지 않는다.
    ("tests/archive/test_archive_collection_view.py", "archive.queries"): frozenset(
        {"ARCHIVE_COLLECTION_PAGE_SIZE"}
    ),
    # MAX_PHOTOS_PER_RECORD 상수만 임포트해 사진 업로드 멱등성 테스트에서
    # 상한까지 채울 미토큰 사진 개수를 계산한다 — 서비스 함수는 호출하지
    # 않는다.
    ("tests/archive/test_visit_records_api.py", "archive.services"): frozenset(
        {"MAX_PHOTOS_PER_RECORD"}
    ),
}

# 테스트 파일이 특정 이름이 아니라 services/queries 모듈 전체를
# (`import <app>.services` 또는 `from <app> import services`) 임포트할 때
# 쓰는 표식이다 — 이 경우 이름 단위로 허용할 게 없으므로, "*" 자체가 허용
# 목록에 없는 한 이런 임포트는 항상 위반이다.
_WHOLE_MODULE_IMPORT = "*"


def _imported_names_by_service_or_query_module(module_path, apps):
    """테스트 파일에서 {"<app>.services" 또는 "<app>.queries": {임포트된 이름}}을
    돌려준다. `import <app>.services`, `from <app>.services import X`,
    `from <app> import services` 세 가지 임포트 표기를 같은 모듈 키로
    합친다. 이름 없이 모듈 전체를 임포트한 경우 "*" 표식으로 기록한다
    (_WHOLE_MODULE_IMPORT 참고)."""
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
    """파일 안의 테스트 함수 중 client/admin_client/user_client/staff_client
    파라미터를 선언한 것이 하나라도 있으면 True — 호출부의 변수명을 추측하는
    게 아니라 `def test_...(...)` 시그니처의 인자 이름이라는 구조적 AST
    사실로 판정한다."""
    tree = ast.parse(path.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            if any(arg.arg in _CLIENT_FAMILY_FIXTURE_NAMES for arg in node.args.args):
                return True
    return False


def test_api_view_계층_테스트_파일은_서비스_쿼리_계층을_임포트하지_않는다():
    """API/뷰 계층 테스트 파일은 HTTP/SSR 경계만 검증해야 한다. services/queries
    모듈에 직접 손을 대야 하는 테스트는 전용 *_services.py / *_queries.py
    파일로 옮겨야 한다 — "파일명 = 검증 계층" 규약이다.

    대상 판정은 두 신호를 함께 쓴다 — 파일명 패턴(*_api.py / *_view(s).py),
    그리고 파일명과 무관하게 client 계열 픽스처 파라미터를 선언한 모든 테스트
    파일(HTTP/SSR을 검증한다는 뜻이므로). 정당한 좁은 예외는
    ALLOWED_SERVICE_OR_QUERY_IMPORTS_IN_API_OR_VIEW_TESTS에 근거 주석과 함께
    이름 단위로 등록한다.
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
