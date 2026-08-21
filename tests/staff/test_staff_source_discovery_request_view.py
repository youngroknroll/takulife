"""수집처 탐색 요청(POST /staff/source-discovery/request/) 뷰 검증.

로컬 러너 heartbeat가 신선할 때만 SourceDiscoveryRun을 pending으로 생성하고
감사 로그를 남긴다. 러너 오프라인이거나 이미 활성 실행이 있으면 안내
메시지만 보여주고 아무것도 만들지 않는다(tests/staff/test_staff_draft_discovery_run_view.py의
의도된 무동작 관행과 동일).
"""
import pytest
from django.urls import reverse

from drafts.discovery_runs import record_heartbeat
from drafts.models import SourceDiscoveryRun
from staff.models import StaffActionLog


pytestmark = pytest.mark.web


def _request_url():
    return reverse("staff:source-discovery-request")


@pytest.mark.django_db
def test_탐색_요청은_스태프_권한과_POST가_필요하고_GET은_대시보드로_리다이렉트된다(client, make_user, staff_client):
    non_staff = make_user()
    client.force_login(non_staff)

    resp = client.post(_request_url())

    assert resp.status_code == 403

    staff, staff_http_client = staff_client()

    resp = staff_http_client.get(_request_url())

    assert resp.status_code == 302
    assert resp.url == "/staff/dashboard/"


@pytest.mark.django_db
def test_러너가_오프라인이면_탐색_요청이_거부되고_이유_메시지가_남는다(staff_client):
    staff, client = staff_client()

    resp = client.post(_request_url(), follow=True)

    assert resp.status_code == 200
    assert resp.redirect_chain[-1][0] == "/staff/dashboard/"
    messages = [str(m) for m in resp.context["messages"]]
    assert any("로컬 러너 오프라인" in m for m in messages)
    assert SourceDiscoveryRun.objects.count() == 0
    assert not StaffActionLog.objects.filter(action=StaffActionLog.Action.SOURCE_DISCOVER).exists()


@pytest.mark.django_db
def test_활성_실행이_있으면_탐색_요청이_거부된다(staff_client):
    record_heartbeat(provider="claude-code")
    staff, client = staff_client()
    SourceDiscoveryRun.objects.create(status=SourceDiscoveryRun.Status.PENDING)

    resp = client.post(_request_url(), follow=True)

    assert resp.status_code == 200
    assert resp.redirect_chain[-1][0] == "/staff/dashboard/"
    messages = [str(m) for m in resp.context["messages"]]
    assert messages
    assert SourceDiscoveryRun.objects.count() == 1
    assert not StaffActionLog.objects.filter(action=StaffActionLog.Action.SOURCE_DISCOVER).exists()


@pytest.mark.django_db
def test_온라인이면_탐색_실행이_생성되고_감사로그가_남는다(staff_client):
    record_heartbeat(provider="claude-code")
    staff, client = staff_client()

    resp = client.post(_request_url(), follow=True)

    assert resp.status_code == 200
    assert resp.redirect_chain[-1][0] == "/staff/dashboard/"
    messages = [str(m) for m in resp.context["messages"]]
    assert messages

    run = SourceDiscoveryRun.objects.get()
    assert run.status == SourceDiscoveryRun.Status.PENDING
    assert run.requested_by_id == staff.id

    log = StaffActionLog.objects.get(action=StaffActionLog.Action.SOURCE_DISCOVER)
    assert log.actor_id == staff.id
