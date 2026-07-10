"""core.views.legal_privacy / legal_terms — smoke coverage for the two
legal informational pages (/legal/privacy/, /legal/terms/).

Render-only views with no auth requirement; these are deliberately smoke
tests (200 + a key phrase), not exhaustive content assertions — see
.docs/plans/2026-07-10-legal-pages-plan.md §4 commit 5.
"""


def test_privacy_page_renders_for_anonymous_user(client):
    resp = client.get("/legal/privacy/")

    assert resp.status_code == 200
    assert "개인정보처리방침" in resp.content.decode()


def test_terms_page_renders_for_anonymous_user(client):
    resp = client.get("/legal/terms/")

    assert resp.status_code == 200
    assert "이용약관" in resp.content.decode()
