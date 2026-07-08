"""Drafts-domain fixtures: httpx transport/resolver stand-ins and sample
content builders shared across the fetching/robots/discovery/LLM test files.
"""
import socket

import httpx
import pytest

import drafts.fetching as fetching


@pytest.fixture
def install_mock_transport():
    """Route drafts.fetching's httpx.Client through an in-process handler —
    no real network I/O.

    Pass `stub_validate_fetch_url=True` for tests that only care about fetch
    mechanics (redirect cap, content-type/size limits, decode) and want the
    real SSRF gate out of the way; leave it False (default) for tests that
    deliberately exercise validate_fetch_url's own logic.
    """
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
    """Build a fake getaddrinfo-style resolver.

    Pass a single IP string to resolve any queried host to that one address,
    or a dict mapping hostname -> IP when different hosts (e.g. a redirect
    target) must resolve differently within the same test.
    """
    def _make(ip_or_by_host, port=443):
        def _resolve(host, _port, *, type=None):
            ip = ip_or_by_host[host] if isinstance(ip_or_by_host, dict) else ip_or_by_host
            return [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip, port))]

        return _resolve

    return _make


@pytest.fixture
def rss_xml():
    """Build a minimal single-item WordPress-style RSS feed. `link` is the
    item's own <link> text; `description_anchors` is a list of raw href
    strings embedded as <a href="..."> markup inside the <description>
    CDATA block, matching how atzip's roundup posts link out.
    `content_encoded_anchors`, when given, additionally embeds a
    <content:encoded> CDATA block (WordPress's full-post-HTML field) and
    declares the feed's real xmlns:content namespace on <rss> — matching
    atzip.kr/feed/'s actual structure, where <description> holds only an
    excerpt + a self-domain "read more" anchor and the real body HTML (with
    outbound official links) lives in <content:encoded>."""
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
    """Build a minimal sitemap.xml, including the sitemaps.org xmlns
    declaration real sitemaps (aniplustv) ship with. Each positional arg is
    either a bare loc string, or a (loc, lastmod-or-None) tuple — real
    sitemaps do not guarantee every <url> carries a <lastmod> sibling."""
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
    """A raw_title/raw_text pair shared by the LLM-extraction test files."""
    return {
        "raw_title": "IVE Popup Store",
        "raw_text": "서울 홍대 2026-07-01 부터 2026-07-20 까지 IVE 팝업 스토어 진행",
    }
