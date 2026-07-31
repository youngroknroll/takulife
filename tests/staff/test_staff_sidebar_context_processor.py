"""B4: 사이드바 배지 카운트 컨텍스트 프로세서.

`/staff/*`가 아닌 요청에서는 draft_review_stats()를 호출하지 않는다 — 소비자
페이지 요청마다 쿼리가 늘어나면 안 된다(계획서 B4 경고).
"""
from types import SimpleNamespace

import pytest

from drafts.models import EventDraft
from staff.context_processors import sidebar_badge_counts

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_resolver_match이_없으면_빈_컨텍스트를_반환한다():
    """미들웨어 순서·404 경로 등 resolver_match가 None인 경우를 대비한다."""
    request = SimpleNamespace(resolver_match=None)

    assert sidebar_badge_counts(request) == {}


@pytest.mark.django_db
def test_resolver_match_속성_자체가_없어도_빈_컨텍스트를_반환한다():
    request = SimpleNamespace()

    assert sidebar_badge_counts(request) == {}


@pytest.mark.django_db
def test_staff_네임스페이스가_아니면_빈_컨텍스트를_반환한다():
    request = SimpleNamespace(resolver_match=SimpleNamespace(app_name="events"))

    assert sidebar_badge_counts(request) == {}


@pytest.mark.django_db
def test_staff_네임스페이스면_대기중_드래프트_건수를_담는다(make_draft):
    make_draft("https://example.com/sidebar-pending-1")
    make_draft("https://example.com/sidebar-pending-2")
    make_draft(
        "https://example.com/sidebar-approved",
        review_status=EventDraft.ReviewStatus.APPROVED,
    )
    request = SimpleNamespace(resolver_match=SimpleNamespace(app_name="staff"))

    assert sidebar_badge_counts(request) == {"sidebar_pending_draft_count": 2}


@pytest.mark.django_db
def test_스태프_콘솔_페이지_응답_컨텍스트에_사이드바_배지_카운트가_있다(staff_client, make_draft):
    make_draft("https://example.com/sidebar-http-pending")

    _, client = staff_client()
    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    assert resp.context["sidebar_pending_draft_count"] == 1


@pytest.mark.django_db
def test_소비자_홈_페이지_응답_컨텍스트에는_사이드바_배지_카운트가_없다(client):
    resp = client.get("/")

    assert resp.status_code == 200
    assert "sidebar_pending_draft_count" not in resp.context
