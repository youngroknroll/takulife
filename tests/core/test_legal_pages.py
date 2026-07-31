"""core.views.legal_privacy / legal_terms — 법적 안내 페이지 두 개(/legal/privacy/,
/legal/terms/)에 대한 스모크 검증.

인증이 필요 없는 렌더 전용 뷰다. 일부러 전체 내용을 단언하지 않고 200과
핵심 문구만 확인하는 스모크 테스트다 — .docs/plans/2026-07-10-legal-pages-plan.md
§4 참고.
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
