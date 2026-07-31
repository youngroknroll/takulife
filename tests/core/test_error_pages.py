"""커스텀 404 / 500 오류 템플릿(templates/404.html, templates/500.html).

Django 테스트 환경은 세션 전체에서 ``settings.DEBUG = False``를 강제하므로
(django.test.utils.setup_test_environment), 해석되지 않는 URL과 처리되지
않은 뷰 예외는 Django의 DEBUG=True 트레이스백이 아니라 실제
handler404/handler500 경로와 프로젝트 브랜드 템플릿을 탄다.
tests/auth/test_auth_rate_limit.py의 429.html 검증과 같은 방식이다.
"""
import pytest

pytestmark = pytest.mark.web


def test_존재하지_않는_경로에_접근하면_커스텀_404_페이지가_홈_링크와_함께_렌더링된다(client):
    resp = client.get("/this-page-does-not-exist/")

    assert resp.status_code == 404
    assert "404.html" in [t.name for t in resp.templates if t.name]
    body = resp.content.decode("utf-8", "ignore")
    assert "takulife" in body
    assert 'href="/"' in body
    assert "ERROR 404" in body


def test_핸들러가_예외를_던지면_요청_컨텍스트_없이도_커스텀_500_페이지가_렌더링된다(client, monkeypatch, db):
    """Django 기본 500 핸들러(django/views/defaults.py::server_error)는
    context도 request도 없이 ``template.render()``로 templates/500.html을
    렌더한다 — 이 페이지에서는 context processor가 전혀 실행되지 않는다.
    "/"에서 처리되지 않은 뷰 예외를 흉내내 그 정확한 경로를 타면서
    500.html이 템플릿 오류 없이 여전히 렌더되는지 확인한다. ``db`` 픽스처가
    없으면 monkeypatch가 걸리기도 전에 DB 접근이 막혀 엉뚱한 이유로 500이
    난다."""

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated view failure")

    monkeypatch.setattr("core.views.events.list_published_events", _boom)
    client.raise_request_exception = False

    resp = client.get("/")

    assert resp.status_code == 500
    assert "500.html" in [t.name for t in resp.templates if t.name]
    body = resp.content.decode("utf-8", "ignore")
    assert "takulife" in body
    assert 'href="mailto:"' not in body
    assert "ERROR 500" in body


def test_정상_홈_페이지_렌더링에서는_푸터가_실제_문의_메일_링크를_유지한다(client, settings, db):
    """위 500 페이지 수정에 대한 회귀 가드: core.context_processors.support_email이
    실행되는 정상 페이지 렌더에서는 실제 mailto 문의 링크가 그대로
    유지돼야 한다."""

    resp = client.get("/")

    assert resp.status_code == 200
    body = resp.content.decode("utf-8", "ignore")
    assert f'href="mailto:{settings.SUPPORT_EMAIL}"' in body
