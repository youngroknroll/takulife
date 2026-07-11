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
