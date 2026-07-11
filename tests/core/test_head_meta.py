"""templates/base.html — favicon + meta description + Open Graph tags.

The shared head (templates/base.html) previously had no favicon and no
meta description / Open Graph tags, so a shared link preview shows only
a bare URL. This is a smoke test against the home page response since
every page inherits templates/base.html and gets these tags automatically.
"""
import pytest


@pytest.mark.django_db
def test_home_page_includes_favicon_link(client):
    resp = client.get("/")

    assert resp.status_code == 200
    assert '<link rel="icon"' in resp.content.decode()


@pytest.mark.django_db
def test_home_page_includes_meta_description(client):
    resp = client.get("/")

    assert resp.status_code == 200
    assert '<meta name="description"' in resp.content.decode()


@pytest.mark.django_db
def test_home_page_includes_open_graph_tags(client):
    resp = client.get("/")

    content = resp.content.decode()
    assert 'property="og:title"' in content
    assert 'property="og:description"' in content
    assert 'property="og:type"' in content


@pytest.mark.django_db
def test_event_detail_og_title_includes_event_title(client, make_event):
    event = make_event(title="공개 행사 오픈")
    resp = client.get(f"/events/{event.id}/")

    content = resp.content.decode()
    assert resp.status_code == 200
    assert '<meta property="og:title" content="takulife | 공개 행사 오픈">' in content


@pytest.mark.django_db
def test_legal_privacy_page_og_title_overrides_default(client):
    resp = client.get("/legal/privacy/")

    content = resp.content.decode()
    assert resp.status_code == 200
    assert '<meta property="og:title" content="개인정보처리방침 — takulife">' in content


@pytest.mark.django_db
def test_event_detail_og_title_escapes_special_characters(client, make_event):
    event = make_event(title='<script>alert("x")</script> & 굿즈전')
    resp = client.get(f"/events/{event.id}/")

    content = resp.content.decode()
    assert resp.status_code == 200
    assert "<script>alert" not in content
    assert (
        '<meta property="og:title" '
        'content="takulife | &lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt; '
        '&amp; 굿즈전">' in content
    )


@pytest.mark.django_db
def test_private_archive_page_keeps_default_og_title(client, make_user):
    client.force_login(make_user())
    resp = client.get("/archive/")

    content = resp.content.decode()
    assert resp.status_code == 200
    assert '<meta property="og:title" content="takulife">' in content
