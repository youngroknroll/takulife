"""templates/base.html — favicon + meta description + Open Graph tags.

The shared head (templates/base.html) previously had no favicon and no
meta description / Open Graph tags, so a shared link preview shows only
a bare URL. This is a smoke test against the home page response since
every page inherits templates/base.html and gets these tags automatically.
"""
import pytest

pytestmark = pytest.mark.web


@pytest.mark.django_db
def test_홈_페이지는_favicon_링크를_포함한다(client):
    resp = client.get("/")

    assert resp.status_code == 200
    assert '<link rel="icon"' in resp.content.decode()


@pytest.mark.django_db
def test_홈_페이지는_meta_description을_포함한다(client):
    resp = client.get("/")

    assert resp.status_code == 200
    assert '<meta name="description"' in resp.content.decode()


@pytest.mark.django_db
def test_홈_페이지는_오픈그래프_태그를_포함한다(client):
    resp = client.get("/")

    content = resp.content.decode()
    assert 'property="og:title"' in content
    assert 'property="og:description"' in content
    assert 'property="og:type"' in content


@pytest.mark.django_db
def test_행사_상세_페이지의_og_title은_행사_제목을_포함한다(client, make_event):
    event = make_event(title="공개 행사 오픈")
    resp = client.get(f"/events/{event.id}/")

    content = resp.content.decode()
    assert resp.status_code == 200
    assert '<meta property="og:title" content="takulife | 공개 행사 오픈">' in content


@pytest.mark.django_db
def test_개인정보처리방침_페이지는_기본_og_title을_페이지_전용_제목으로_재정의한다(client):
    resp = client.get("/legal/privacy/")

    content = resp.content.decode()
    assert resp.status_code == 200
    assert '<meta property="og:title" content="개인정보처리방침 — takulife">' in content


@pytest.mark.django_db
def test_행사_상세_페이지의_og_title은_특수문자를_이스케이프한다(client, make_event):
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
def test_비공개_아카이브_페이지는_기본_og_title을_유지한다(client, make_user):
    client.force_login(make_user())
    resp = client.get("/archive/")

    content = resp.content.decode()
    assert resp.status_code == 200
    assert '<meta property="og:title" content="takulife">' in content
