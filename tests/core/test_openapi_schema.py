"""OpenAPI 스키마·문서 엔드포인트 계약: 응답 형태(web)와 경로 완전성(contract)을 검증한다."""
import re

import pytest
from django.conf import settings
from django.urls import URLResolver, get_resolver


_HTTP_METHODS = {"get", "post", "put", "patch", "delete", "head", "options", "trace"}


def _collect_api_path_templates():
    """루트 urlconf를 재귀 순회해 "/api/"로 시작하는 경로 템플릿 집합을 만든다.
    하드코딩 목록이 아니라 urlconf에서 직접 파생해야 라우트를 지우거나
    바꿔도 이 대조가 뮤테이션을 탐지한다."""
    resolver = get_resolver()
    templates = set()

    def _walk(patterns, prefix):
        for entry in patterns:
            full_prefix = prefix + str(entry.pattern)
            if isinstance(entry, URLResolver):
                _walk(entry.url_patterns, full_prefix)
            elif full_prefix.startswith("api/"):
                templates.add("/" + full_prefix)

    _walk(resolver.url_patterns, "")
    return templates


_PATH_PARAM_RE = re.compile(r"<(?:[^:<>]+:)?([^<>]+)>")


def _normalize_path(path):
    """Django 경로 변환기(`<int:pk>` 등)를 drf-spectacular 스키마 키 형식으로
    바꾼다. DRF 기본 설정 SCHEMA_COERCE_PATH_PK=True(이 저장소는 오버라이드하지
    않음)가 파라미터명 "pk"를 "id"로 강제 치환하므로 여기서도 같은 규칙을
    적용한다 — 그 외 이름은 변환기 타입만 벗기고 그대로 둔다."""

    def _replace(match):
        name = match.group(1)
        return "{id}" if name == "pk" else "{" + name + "}"

    return _PATH_PARAM_RE.sub(_replace, path)


def _is_documentation_endpoint(path):
    return path.startswith("/api/schema") or path.startswith("/api/docs")


# 러너 경계는 비밀 토큰 기반 기계 간 API라 공개 문서에서 의도적으로 뺐다
# (drafts/runner_views.py의 @extend_schema(exclude=True)와 짝을 이루는 결정 —
# 완전성 가드가 이를 누락으로 오판하지 않도록 여기서도 명시한다).
_INTENTIONALLY_UNDOCUMENTED_PREFIXES = ("/api/discovery/runner/",)


def _is_intentionally_undocumented(path):
    return path.startswith(_INTENTIONALLY_UNDOCUMENTED_PREFIXES)


@pytest.mark.web
def test_익명_사용자가_스키마를_요청하면_OpenAPI_문서를_받는다(client):
    response = client.get("/api/schema/", {"format": "json"})

    assert response.status_code == 200
    body = response.json()
    assert body["openapi"].startswith("3.")
    assert "/api/events/" in body["paths"]


@pytest.mark.web
def test_익명_사용자가_문서_페이지를_요청하면_스웨거_UI가_렌더된다(client):
    response = client.get("/api/docs/")

    assert response.status_code == 200
    assert "text/html" in response["Content-Type"]
    assert "swagger-ui" in response.content.decode()


@pytest.mark.contract
def test_스키마_생성시_등록된_API_경로가_모두_포함된다():
    from drf_spectacular.generators import SchemaGenerator

    urlconf_paths = {
        _normalize_path(path)
        for path in _collect_api_path_templates()
        if not _is_documentation_endpoint(path) and not _is_intentionally_undocumented(path)
    }
    assert urlconf_paths, "urlconf에서 파생된 /api/ 경로가 비어 있다 — 스캔이 잘못됐다"

    generator = SchemaGenerator()
    schema = generator.get_schema(request=None, public=True)

    assert urlconf_paths <= set(schema["paths"]), urlconf_paths - set(schema["paths"])


@pytest.mark.contract
def test_공개_스키마의_모든_경로는_api_프리픽스로_시작한다():
    """스키마는 공개 API 문서다 — /staff/ 콘솔 전용 DRF 뷰가 섞여 들어오면
    운영 내부 엔드포인트가 공개 계약처럼 노출된다."""
    from drf_spectacular.generators import SchemaGenerator

    generator = SchemaGenerator()
    schema = generator.get_schema(request=None, public=True)

    non_api_paths = {path for path in schema["paths"] if not path.startswith("/api/")}

    assert not non_api_paths, non_api_paths


@pytest.mark.contract
@pytest.mark.django_db
def test_스키마_생성은_분석_이벤트를_기록하지_않는다():
    """django_db가 꼭 필요하다 — record_event의 best-effort except가 커밋
    검증 없이는 차단 예외를 삼켜, 부작용이 실제로 일어났는지 이 테스트가
    가릴 수 없게 만든다."""
    from drf_spectacular.generators import SchemaGenerator

    from core.models import AnalyticsEvent

    generator = SchemaGenerator()
    generator.get_schema(request=None, public=True)

    assert AnalyticsEvent.objects.count() == 0


@pytest.mark.contract
def test_공개_스키마의_모든_operation은_선언된_태그만_사용한다():
    """@extend_schema_view 키 오기입(예: list/create가 아니라 get/post여야
    하는데 무시되는 경우) 등으로 명시 태그가 조용히 적용되지 않으면
    drf-spectacular가 URL에서 파생한 태그로 조용히 떨어진다 — 그 회귀를 잡는다."""
    from drf_spectacular.generators import SchemaGenerator

    declared_tags = {tag["name"] for tag in settings.SPECTACULAR_SETTINGS["TAGS"]}
    assert declared_tags, "SPECTACULAR_SETTINGS['TAGS']가 비어 있다"

    generator = SchemaGenerator()
    schema = generator.get_schema(request=None, public=True)

    violations = []
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            if method.lower() not in _HTTP_METHODS:
                continue
            for tag in operation.get("tags", []):
                if tag not in declared_tags:
                    violations.append((path, method, tag))

    assert not violations, violations
