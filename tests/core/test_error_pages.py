"""Custom 404 / 500 error templates (templates/404.html, templates/500.html).

Django's test environment forces ``settings.DEBUG = False`` for the whole
session (django.test.utils.setup_test_environment), so an unresolved URL and
an unhandled view exception exercise the real handler404 / handler500
codepath and the project's branded templates — not Django's DEBUG=True
tracebacks. Mirrors the 429.html coverage in
tests/auth/test_auth_rate_limit.py::test_rate_limited_response_renders_localized_page.
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


def test_핸들러가_예외를_던지면_요청_컨텍스트_없이도_커스텀_500_페이지가_렌더링된다(client, monkeypatch):
    """Django's default 500 handler (django/views/defaults.py::server_error)
    renders templates/500.html via ``template.render()`` with NO context and
    NO request — context processors never run for this page. Simulate an
    unhandled view exception on "/" to exercise that exact codepath and
    confirm 500.html still renders (rather than raising a template error)."""

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
    """Regression guard for the 500-page fix above: normal page renders
    (where core.context_processors.support_email does run) must keep the
    real mailto contact link in the footer."""

    resp = client.get("/")

    assert resp.status_code == 200
    body = resp.content.decode("utf-8", "ignore")
    assert f'href="mailto:{settings.SUPPORT_EMAIL}"' in body
