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


@pytest.mark.django_db
def test_home_page_includes_skip_link_to_content(client):
    resp = client.get("/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert '<a class="skip-link" href="#content">본문으로 건너뛰기</a>' in content
    assert 'id="content"' in content


@pytest.mark.django_db
def test_event_list_skip_link_target_exists(client):
    resp = client.get("/events/")

    assert resp.status_code == 200
    content = resp.content.decode()
    assert '<a class="skip-link" href="#content">본문으로 건너뛰기</a>' in content
    assert 'id="content"' in content


@pytest.mark.django_db
def test_staff_dashboard_keeps_its_own_skip_link_only(client, make_user):
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
