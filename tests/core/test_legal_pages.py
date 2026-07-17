"""core.views.legal_privacy / legal_terms — smoke coverage for the two
legal informational pages (/legal/privacy/, /legal/terms/).

Render-only views with no auth requirement; these are deliberately smoke
tests (200 + a key phrase), not exhaustive content assertions — see
.docs/plans/2026-07-10-legal-pages-plan.md §4 commit 5.
"""


import pytest

pytestmark = pytest.mark.web


def test_비로그인_사용자가_개인정보처리방침_페이지에_접근하면_200과_핵심_문구를_응답한다(client):
    resp = client.get("/legal/privacy/")

    assert resp.status_code == 200
    assert "개인정보처리방침" in resp.content.decode()


def test_비로그인_사용자가_이용약관_페이지에_접근하면_200과_핵심_문구를_응답한다(client):
    resp = client.get("/legal/terms/")

    assert resp.status_code == 200
    assert "이용약관" in resp.content.decode()
