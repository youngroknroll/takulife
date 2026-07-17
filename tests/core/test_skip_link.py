"""templates/base.html — "본문으로 건너뛰기" skip link (a11y).

The public shell had no skip link (only the staff console did), so keyboard
users had to tab through the whole header/nav on every page. base.html now
renders one pointed at #content, which every non-staff page template's
<main> carries. Staff pages keep their own (targets #staff-main, from
_console_shell.html) and suppress the public one via the skip_link block —
this is a smoke test that both shells end up with exactly one, pointed at
a target that actually exists.
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
    # The staff console's own skip link (targets #staff-main) is present…
    assert '<a class="skip-link" href="#staff-main">본문으로 건너뛰기</a>' in content
    # …and the public one (#content, which staff pages don't have) is not
    # duplicated in — exactly one .skip-link on the page.
    assert content.count('class="skip-link"') == 1
