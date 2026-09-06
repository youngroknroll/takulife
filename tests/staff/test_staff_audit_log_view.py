"""감사 로그 화면(/staff/audit-log/) 검증(B8, N2).

D9: 운영자(is_staff)는 행위자/행동/대상/시각만 볼 수 있고 ip_address/
user_agent는 볼 수 없다(슈퍼유저 전용, staff/admin.py). 이 화면의 컨텍스트
자체에 그 두 필드가 실려서는 안 된다.
"""
import pytest
from django.urls import reverse

from staff.models import StaffActionLog
from staff.views.audit_log import STAFF_ACTION_LOG_PAGE_SIZE

pytestmark = pytest.mark.web


def audit_log_url():
    return reverse("staff:audit-log")


def _make_approvable_draft(make_draft, source_url, *, extracted_title, **overrides):
    """approve_draft는 제목이 없으면 DraftPublicationTitleError로 거부한다
    (drafts/services.py). make_draft 기본값에는 extracted_title이 없어
    그대로 쓰면 감사 로그 테스트가 "승인이 이미 성공했다"는 전제를 조용히
    깨뜨린다 — 그래서 이 헬퍼는 extracted_title을 기본값 없이 강제한다.
    """
    return make_draft(source_url, extracted_title=extracted_title, **overrides)


def _approve_draft(client, draft_id, **extra):
    """승인 POST 응답을 검증하고 넘어간다. 실패해도 조용히 지나가면 감사
    로그가 비어 있는 채로 이후 단언(len==1 등)에서야 원인 불명으로 깨진다."""
    resp = client.post(
        reverse("staff:draft-approve", kwargs={"draft_id": draft_id}), **extra
    )
    assert resp.status_code == 200, resp.content
    return resp


def _reject_draft(client, draft_id, **extra):
    resp = client.post(
        reverse("staff:draft-reject", kwargs={"draft_id": draft_id}), **extra
    )
    assert resp.status_code == 200, resp.content
    return resp


@pytest.mark.django_db
def test_비로그인_사용자의_감사_로그_접근은_로그인_페이지로_리다이렉트된다(client):
    resp = client.get(audit_log_url())

    assert resp.status_code == 302
    assert resp.url.startswith("/accounts/login/")


@pytest.mark.django_db
def test_일반_사용자는_감사_로그에_접근할_수_없다(client, make_user):
    user = make_user()
    client.force_login(user)

    resp = client.get(audit_log_url())

    assert resp.status_code == 403


@pytest.mark.django_db
def test_스태프는_감사_로그_목록을_볼_수_있다(staff_client, make_draft):
    staff, client = staff_client()
    draft = _make_approvable_draft(
        make_draft, "https://example.com/audit-log-1", extracted_title="감사 대상"
    )
    _approve_draft(client, draft.id)

    resp = client.get(audit_log_url())

    assert resp.status_code == 200
    rows = resp.context["log_rows"]
    assert len(rows) == 1
    assert rows[0]["action"] == StaffActionLog.Action.APPROVE
    assert rows[0]["action_label"] == "승인"
    assert rows[0]["actor_email"] == staff.email
    assert rows[0]["target_label"] == "https://example.com/audit-log-1"


@pytest.mark.django_db
def test_감사_로그_행_컨텍스트에는_ip_주소나_user_agent가_없다(staff_client, make_draft):
    """D9: 요약 dict 자체가 그 필드를 담지 않는다."""
    staff, client = staff_client()
    draft = _make_approvable_draft(
        make_draft, "https://example.com/audit-log-privacy", extracted_title="비공개 확인용"
    )
    _approve_draft(
        client,
        draft.id,
        REMOTE_ADDR="203.0.113.11",
        HTTP_USER_AGENT="pytest-agent/9.0",
    )

    resp = client.get(audit_log_url())

    row = resp.context["log_rows"][0]
    assert "ip_address" not in row
    assert "user_agent" not in row
    body = resp.content.decode()
    assert "203.0.113.11" not in body
    assert "pytest-agent/9.0" not in body


@pytest.mark.django_db
def test_action_필터를_적용하면_일치하는_로그만_보여준다(staff_client, make_draft):
    staff, client = staff_client()
    approved = _make_approvable_draft(
        make_draft, "https://example.com/audit-filter-approve", extracted_title="필터 승인 대상"
    )
    rejected = make_draft("https://example.com/audit-filter-reject")
    _approve_draft(client, approved.id)
    _reject_draft(client, rejected.id)

    resp = client.get(f"{audit_log_url()}?action=reject")

    assert resp.status_code == 200
    rows = resp.context["log_rows"]
    assert len(rows) == 1
    assert rows[0]["action"] == StaffActionLog.Action.REJECT


@pytest.mark.django_db
def test_알_수_없는_action_값은_전체_보기로_대체된다(staff_client, make_draft):
    staff, client = staff_client()
    draft = _make_approvable_draft(
        make_draft, "https://example.com/audit-unknown-filter", extracted_title="알수없는 필터 대상"
    )
    _approve_draft(client, draft.id)

    resp = client.get(f"{audit_log_url()}?action=garbage")

    assert resp.status_code == 200
    assert resp.context["selected_action"] == ""
    assert len(resp.context["log_rows"]) == 1


@pytest.mark.django_db
def test_감사_로그가_없으면_빈_목록_안내를_보여준다(staff_client):
    _, client = staff_client()

    resp = client.get(audit_log_url())

    assert resp.status_code == 200
    assert resp.context["log_rows"] == []


@pytest.mark.django_db
def test_감사_로그_첫_페이지는_페이지_크기만큼만_보여준다(staff_client, make_draft):
    staff, client = staff_client()
    for i in range(STAFF_ACTION_LOG_PAGE_SIZE + 1):
        draft = _make_approvable_draft(
            make_draft, f"https://example.com/audit-page-{i}", extracted_title=f"페이지 대상 {i}"
        )
        _approve_draft(client, draft.id)

    resp = client.get(audit_log_url())

    assert resp.status_code == 200
    page_obj = resp.context["page_obj"]
    assert page_obj.paginator.count == STAFF_ACTION_LOG_PAGE_SIZE + 1
    assert len(page_obj.object_list) == STAFF_ACTION_LOG_PAGE_SIZE


@pytest.mark.django_db
def test_대시보드_최근_처리_내역에도_ip_주소나_user_agent가_없다(staff_client, make_draft):
    """대시보드는 감사 로그와 달리 StaffActionLog 모델 인스턴스를 그대로 넘긴다.

    지금 안 새는 근거가 "템플릿이 그 필드를 안 썼다"뿐이라, 한 줄만 늘어도
    운영자 전원에게 다른 스태프의 접속 IP가 보인다.
    """
    staff, client = staff_client()
    draft = _make_approvable_draft(
        make_draft, "https://example.com/dashboard-privacy", extracted_title="대시보드 확인용"
    )
    _approve_draft(
        client,
        draft.id,
        REMOTE_ADDR="203.0.113.77",
        HTTP_USER_AGENT="pytest-dashboard-agent/1.0",
    )

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    body = resp.content.decode()
    assert "203.0.113.77" not in body
    assert "pytest-dashboard-agent/1.0" not in body


# 트랙 19 H1: 계정 운영 행동(target_user)의 감사 표시 비식별화(T11, SRR
# Medium). 이 화면은 staff_console_required(is_staff 전체)라, 계정 운영
# 관문(superuser 한정)의 대상 이메일을 그대로 보여주면 권한 경계를
# 우회해 노출된다 — 대상 라벨은 계정 번호로만 렌더하고 검색도 매칭하지
# 않는다.


@pytest.mark.django_db
def test_계정_행동_로그_행의_대상_라벨은_계정_번호이고_본문에_대상_이메일이_없다(staff_client, make_user):
    staff, client = staff_client()  # 슈퍼유저 아닌 운영자
    target = make_user(email="account-log-target@example.com")
    StaffActionLog.objects.create(
        actor=staff,
        action=StaffActionLog.Action.STAFF_GRANT,
        target_user=target,
    )

    resp = client.get(audit_log_url())

    assert resp.status_code == 200
    row = resp.context["log_rows"][0]
    assert row["target_label"] == f"계정 #{target.pk}"
    assert target.email not in resp.content.decode()


@pytest.mark.django_db
def test_슈퍼유저의_감사_로그_계정_행에는_계정_상세_링크가_있다(staff_client, make_user):
    staff, client = staff_client(is_superuser=True)
    target = make_user(email="account-log-link-target@example.com")
    StaffActionLog.objects.create(
        actor=staff,
        action=StaffActionLog.Action.STAFF_GRANT,
        target_user=target,
    )

    resp = client.get(audit_log_url())

    assert resp.status_code == 200
    assert f"/staff/accounts/{target.pk}/" in resp.content.decode()


@pytest.mark.django_db
def test_감사_로그_q_검색어는_대상_계정_이메일과_매칭하지_않는다(staff_client, make_user):
    staff, client = staff_client()
    target = make_user(email="search-target-account@example.com")
    StaffActionLog.objects.create(
        actor=staff,
        action=StaffActionLog.Action.STAFF_GRANT,
        target_user=target,
    )

    resp = client.get(f"{audit_log_url()}?q=search-target-account")

    assert resp.status_code == 200
    assert resp.context["log_rows"] == []


@pytest.mark.django_db
def test_대시보드_최근_처리_내역의_계정_행동_행에_대상_이메일이_없다(staff_client, make_user):
    staff, client = staff_client()
    target = make_user(email="dashboard-target-account@example.com")
    StaffActionLog.objects.create(
        actor=staff,
        action=StaffActionLog.Action.STAFF_GRANT,
        target_user=target,
    )

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    assert target.email not in resp.content.decode()

