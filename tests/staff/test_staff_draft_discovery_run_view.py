"""수집 실행(POST /staff/draft-discovery/run/) 뷰 검증.

discover_drafts 관리 명령을 동기 호출해 결과를 메시지로 보여주고 대시보드로
리다이렉트한다. 플래그가 꺼져 있거나 활성 소스가 없을 때는 명령을 실행하지
않고 감사 로그도 남기지 않는다(의도된 무동작). 실제 실행(성공/부분실패/예외)은
전부 감사 로그로 남긴다. discover_drafts 자체 동작은
tests/test_discover_drafts_command.py에서 다루므로 여기서는 다루지 않는다.
"""
import pytest
from django.core.management import CommandError

from staff.models import StaffActionLog


RUN_URL = "/staff/draft-discovery/run/"

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_비로그인_사용자가_수집_실행을_요청하면_로그인_페이지로_리다이렉트된다(client):
    resp = client.post(RUN_URL)

    assert resp.status_code == 302
    assert resp.url == f"/accounts/login/?next={RUN_URL}"


@pytest.mark.django_db
def test_스태프가_아닌_사용자가_수집_실행을_요청하면_403을_응답한다(client, make_user):
    user = make_user()
    client.force_login(user)

    resp = client.post(RUN_URL)

    assert resp.status_code == 403


@pytest.mark.django_db
def test_수집_실행_경로에_GET으로_접근하면_405_대신_대시보드로_리다이렉트된다(staff_client):
    staff, client = staff_client()

    resp = client.get(RUN_URL)

    assert resp.status_code == 302
    assert resp.url == "/staff/dashboard/"


@pytest.mark.django_db
def test_수집_기능_플래그가_꺼져_있으면_안내_메시지만_보여주고_명령을_실행하지_않는다(staff_client, settings, monkeypatch, fail_if_called):
    settings.DRAFT_DISCOVERY_ENABLED = False
    staff, client = staff_client()

    monkeypatch.setattr("staff.views.call_command", fail_if_called)

    resp = client.post(RUN_URL, follow=True)

    assert resp.status_code == 200
    messages = [str(m) for m in resp.context["messages"]]
    assert any("DRAFT_DISCOVERY_ENABLED=False" in m for m in messages)
    assert not StaffActionLog.objects.filter(action=StaffActionLog.Action.DRAFT_DISCOVER).exists()


@pytest.mark.django_db
def test_활성_수집_소스가_없으면_안내_메시지만_보여주고_명령을_실행하지_않는다(staff_client, settings, monkeypatch, make_source, fail_if_called):
    settings.DRAFT_DISCOVERY_ENABLED = True
    staff, client = staff_client()
    make_source(name="disabled-source", url="https://example.com/disabled-feed/", enabled=False)

    monkeypatch.setattr("staff.views.call_command", fail_if_called)

    resp = client.post(RUN_URL, follow=True)

    assert resp.status_code == 200
    messages = [str(m) for m in resp.context["messages"]]
    assert any("활성 수집 소스가 없습니다" in m for m in messages)
    assert not StaffActionLog.objects.filter(action=StaffActionLog.Action.DRAFT_DISCOVER).exists()


@pytest.mark.django_db
def test_수집_실행이_성공하면_요약_메시지를_보여주고_감사_로그를_남긴다(staff_client, settings, monkeypatch, make_source):
    settings.DRAFT_DISCOVERY_ENABLED = True
    staff, client = staff_client()
    make_source(name="enabled-source", url="https://example.com/enabled-feed/")

    def _fake_call_command(name, *args, stdout=None, **kwargs):
        assert name == "discover_drafts"
        stdout.write("발견 0건 (상한 도달로 0건 보류) / 생성 0건\n")
        stdout.write("스킵 - 중복 0건, robots 불허 0건, robots 페치 실패 0건, 빈 콘텐츠 0건\n")
        stdout.write("에러 0건\n")

    monkeypatch.setattr("staff.views.call_command", _fake_call_command)

    resp = client.post(RUN_URL, follow=True)

    assert resp.status_code == 200
    messages = [str(m) for m in resp.context["messages"]]
    assert any("생성 0건" in m for m in messages)
    log = StaffActionLog.objects.get(action=StaffActionLog.Action.DRAFT_DISCOVER)
    assert log.actor_id == staff.id


@pytest.mark.django_db
def test_수집_실행이_부분_실패하면_오류_메시지를_보여주고_감사_로그를_남긴다(staff_client, settings, monkeypatch, make_source):
    settings.DRAFT_DISCOVERY_ENABLED = True
    staff, client = staff_client()
    make_source(name="enabled-source", url="https://example.com/enabled-feed/")

    def _fake_call_command(name, *args, stdout=None, **kwargs):
        stdout.write("발견 1건 (상한 도달로 0건 보류) / 생성 0건\n")
        raise CommandError("discover_drafts: 1건 에러 발생 — 위 로그 참고")

    monkeypatch.setattr("staff.views.call_command", _fake_call_command)

    resp = client.post(RUN_URL, follow=True)

    assert resp.status_code == 200
    messages = [str(m) for m in resp.context["messages"]]
    assert any("에러" in m or "실패" in m for m in messages)
    log = StaffActionLog.objects.get(action=StaffActionLog.Action.DRAFT_DISCOVER)
    assert log.actor_id == staff.id


@pytest.mark.django_db
def test_수집_실행_중_예외가_발생해도_전파되지_않고_오류_메시지와_감사_로그를_남긴다(staff_client, settings, monkeypatch, make_source):
    settings.DRAFT_DISCOVERY_ENABLED = True
    staff, client = staff_client()
    make_source(name="enabled-source", url="https://example.com/enabled-feed/")

    def _fake_call_command(name, *args, stdout=None, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("staff.views.call_command", _fake_call_command)

    resp = client.post(RUN_URL, follow=True)

    assert resp.status_code == 200
    messages = [str(m) for m in resp.context["messages"]]
    assert any("오류" in m for m in messages)
    log = StaffActionLog.objects.get(action=StaffActionLog.Action.DRAFT_DISCOVER)
    assert log.actor_id == staff.id
