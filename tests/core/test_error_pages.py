"""Custom 404 / 500 error templates (templates/404.html, templates/500.html).

Django's test environment forces ``settings.DEBUG = False`` for the whole
session (django.test.utils.setup_test_environment), so an unresolved URL and
an unhandled view exception exercise the real handler404 / handler500
codepath and the project's branded templates — not Django's DEBUG=True
tracebacks. Mirrors the 429.html coverage in
tests/auth/test_auth_rate_limit.py::test_rate_limited_response_renders_localized_page.
"""


def test_404_page_uses_custom_template_and_links_home(client):
    resp = client.get("/this-page-does-not-exist/")

    assert resp.status_code == 404
    assert "404.html" in [t.name for t in resp.templates if t.name]
    body = resp.content.decode("utf-8", "ignore")
    assert "takulife" in body
    assert 'href="/"' in body


def test_500_page_renders_without_request_context(client, monkeypatch):
    """Django's default 500 handler (django/views/defaults.py::server_error)
    renders templates/500.html via ``template.render()`` with NO context and
    NO request — context processors never run for this page. Simulate an
    unhandled view exception on "/" to exercise that exact codepath and
    confirm 500.html still renders (rather than raising a template error)."""

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated view failure")

    monkeypatch.setattr("core.views.list_published_events", _boom)
    client.raise_request_exception = False

    resp = client.get("/")

    assert resp.status_code == 500
    assert "500.html" in [t.name for t in resp.templates if t.name]
    body = resp.content.decode("utf-8", "ignore")
    assert "takulife" in body
