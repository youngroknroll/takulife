"""수집 소스 목록 화면(/staff/sources/) 검증(N1).

DraftSource 조회(list_draft_sources)와 행 가공(_build_source_rows)은
이미 대시보드에서 검증됐다 — 여기서는 접근 제어와 새 라우트의 컨텍스트
배선만 확인한다.
"""
import pytest
from django.urls import reverse

from drafts.models import DraftSource

pytestmark = pytest.mark.web


def sources_url():
    return reverse("staff:draft-source-list")


@pytest.mark.django_db
def test_비로그인_사용자의_수집_소스_접근은_로그인_페이지로_리다이렉트된다(client):
    resp = client.get(sources_url())

    assert resp.status_code == 302
    assert resp.url.startswith("/accounts/login/")


@pytest.mark.django_db
def test_일반_사용자는_수집_소스_화면에_접근할_수_없다(client, make_user):
    user = make_user()
    client.force_login(user)

    resp = client.get(sources_url())

    assert resp.status_code == 403


@pytest.mark.django_db
def test_스태프는_등록된_수집_소스_행을_볼_수_있다(staff_client):
    _, client = staff_client()
    DraftSource.objects.create(
        name="공식 트위터",
        url="https://example.com/feed.xml",
        source_type=DraftSource.SourceType.RSS,
        enabled=True,
    )

    resp = client.get(sources_url())

    assert resp.status_code == 200
    rows = resp.context["draft_source_rows"]
    assert len(rows) == 1
    assert rows[0]["source"].name == "공식 트위터"


@pytest.mark.django_db
def test_수집_소스가_없으면_빈_목록으로_렌더링된다(staff_client):
    _, client = staff_client()

    resp = client.get(sources_url())

    assert resp.status_code == 200
    assert resp.context["draft_source_rows"] == []
