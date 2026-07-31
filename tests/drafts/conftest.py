"""drafts 도메인 테스트가 공유하는 fixture 모음: httpx 통신 대역과 샘플 콘텐츠 생성기."""
import socket

import httpx
import pytest

import drafts.fetching as fetching


@pytest.fixture
def install_mock_transport():
    """drafts.fetching의 httpx.Client를 실제 네트워크 없이 인프로세스 핸들러로 대체한다.
    `stub_validate_fetch_url=True`면 SSRF 검사를 우회하고 fetch 동작 자체만 검증한다."""
    def _install(monkeypatch, handler, *, stub_validate_fetch_url=False):
        if stub_validate_fetch_url:
            monkeypatch.setattr(fetching, "validate_fetch_url", lambda *a, **k: None)

        real_client = httpx.Client

        def factory(**kwargs):
            kwargs.pop("transport", None)
            return real_client(transport=httpx.MockTransport(handler), **kwargs)

        monkeypatch.setattr(fetching.httpx, "Client", factory)

    return _install


@pytest.fixture
def fake_resolver():
    """getaddrinfo 형태의 가짜 리졸버를 만든다. 문자열이면 모든 호스트를 그 IP로,
    dict면 호스트별로 다른 IP로 해석한다(리다이렉트 대상 등)."""
    def _make(ip_or_by_host, port=443):
        def _resolve(host, _port, *, type=None):
            ip = ip_or_by_host[host] if isinstance(ip_or_by_host, dict) else ip_or_by_host
            return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip, port))]

        return _resolve

    return _make


@pytest.fixture
def rss_xml():
    """워드프레스 스타일 RSS 피드 1건을 만든다. atzip.kr/feed/의 실제 구조를 본떠
    <description>은 발췌만, 외부 공식 링크는 <content:encoded>(워드프레스 본문 HTML
    필드)에 담기게 한다."""
    def _make(*, link=None, description_anchors=None, content_encoded_anchors=None):
        link_xml = f"<link>{link}</link>" if link else ""
        anchors_html = "".join(f'<a href="{href}">link</a>' for href in (description_anchors or []))
        description_xml = f"<description><![CDATA[{anchors_html}]]></description>" if anchors_html else ""
        encoded_anchors_html = "".join(
            f'<a href="{href}">link</a>' for href in (content_encoded_anchors or [])
        )
        encoded_xml = (
            f"<content:encoded><![CDATA[{encoded_anchors_html}]]></content:encoded>"
            if encoded_anchors_html
            else ""
        )
        content_namespace = (
            ' xmlns:content="http://purl.org/rss/1.0/modules/content/"'
            if content_encoded_anchors
            else ""
        )
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"{content_namespace}><channel><title>atzip</title>
<item>{link_xml}{description_xml}{encoded_xml}</item>
</channel></rss>"""

    return _make


@pytest.fixture
def sitemap_xml():
    """최소 sitemap.xml을 만든다. 실제 사이트맵(aniplustv 등)처럼 모든 <url>이
    <lastmod>을 갖지는 않으므로 (loc, lastmod-or-None) 형태도 받는다."""
    def _make(*locs):
        def _url_xml(entry):
            loc, lastmod = entry if isinstance(entry, tuple) else (entry, None)
            lastmod_xml = f"<lastmod>{lastmod}</lastmod>" if lastmod else ""
            return f"<url><loc>{loc}</loc>{lastmod_xml}</url>"

        url_xml = "".join(_url_xml(entry) for entry in locs)
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{url_xml}</urlset>"""

    return _make


@pytest.fixture
def sample_extraction():
    """LLM 추출 테스트들이 공유하는 raw_title/raw_text 샘플."""
    return {
        "raw_title": "IVE Popup Store",
        "raw_text": "서울 홍대 2026-07-01 부터 2026-07-20 까지 IVE 팝업 스토어 진행",
    }
