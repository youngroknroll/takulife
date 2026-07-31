"""templates/base.html — favicon + meta description + 오픈그래프 태그.

공용 head(templates/base.html)에 원래 favicon도 meta description/오픈그래프
태그도 없어서, 링크를 공유하면 미리보기에 URL만 덩그러니 나왔다. 모든
페이지가 templates/base.html을 상속해 이 태그들을 자동으로 얻으므로, 홈
페이지 응답으로 스모크 테스트한다.
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
