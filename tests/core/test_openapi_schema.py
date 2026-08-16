"""OpenAPI 스키마·문서 엔드포인트 계약: 응답 형태(web)와 경로 완전성(contract)을 검증한다."""
import re

import pytest
from django.urls import URLResolver, get_resolver


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
        if not _is_documentation_endpoint(path)
    }
    assert urlconf_paths, "urlconf에서 파생된 /api/ 경로가 비어 있다 — 스캔이 잘못됐다"

    generator = SchemaGenerator()
    schema = generator.get_schema(request=None, public=True)

    assert urlconf_paths <= set(schema["paths"]), urlconf_paths - set(schema["paths"])
