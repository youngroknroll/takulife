"""templates/base.html — "본문으로 건너뛰기" skip link(접근성).

공개 셸에는 원래 skip link가 없어서(스태프 콘솔에만 있었다) 키보드
사용자는 페이지마다 헤더/내비 전체를 탭으로 넘어가야 했다. base.html이
이제 #content를 가리키는 skip link를 렌더하는데, 이건 스태프가 아닌
모든 페이지 템플릿의 <main>이 갖고 있는 id다. 스태프 페이지는 자기 것
(_console_shell.html의 #staff-main 대상)을 유지하고 skip_link 블록으로
공용 것을 억제한다 — 두 셸 모두 실제로 존재하는 대상을 가리키는 skip
link를 정확히 하나만 갖는지 확인하는 스모크 테스트다.
"""
import pytest

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_홈_페이지는_content로_건너뛰는_skip_link를_포함한다(client):
    resp = client.get("/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert '<a class="skip-link" href="#content">본문으로 건너뛰기</a>' in content
    assert 'id="content"' in content


@pytest.mark.django_db
def test_행사_목록_페이지의_skip_link_대상이_실제로_존재한다(client):
    resp = client.get("/events/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert '<a class="skip-link" href="#content">본문으로 건너뛰기</a>' in content
    assert 'id="content"' in content


@pytest.mark.django_db
def test_스태프_대시보드는_자신의_skip_link만_유지하고_공용_skip_link를_중복하지_않는다(client, make_user):
    staff = make_user(is_staff=True)
    client.force_login(staff)

    resp = client.get("/staff/dashboard/")

    assert resp.status_code == 200
    content = resp.content.decode()
    # 스태프 콘솔 자체의 skip link(#staff-main 대상)는 있고…
    assert '<a class="skip-link" href="#staff-main">본문으로 건너뛰기</a>' in content
    # …공용 것(#content, 스태프 페이지에는 없는 id)은 중복돼 들어가지
    # 않아서 페이지에 .skip-link가 정확히 하나뿐이다.
    assert content.count('class="skip-link"') == 1
