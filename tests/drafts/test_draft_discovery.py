"""Tests for drafts.discovery — pure link-extraction functions for the
auto-discovery pipeline (PR-2 of prompt_plan.md §2-1/§2-4/§2-5).

Pure str fixtures only: no DB, no network. `content` here stands in for what
`fetch_html` already decoded to a Python str, which is why the XML fixtures
below include an encoding declaration — that is the exact case that breaks a
naive `xml.etree.ElementTree.fromstring(str)` call (see §2-4).
"""
import pytest

from drafts.discovery import (
    DiscoveryParseError,
    extract_candidate_urls,
    extract_links_html,
    extract_links_rss,
    extract_links_sitemap,
)


# A billion-laughs style entity-expansion payload, kept small for a fast
# test: a handful of nested entity references rather than the real attack's
# exponential blowup. defusedxml must reject this outright regardless of
# size, so the miniature form still exercises the guard.
ENTITY_EXPANSION_XML = """<?xml version="1.0"?>
<!DOCTYPE rss [
<!ENTITY a "spam">
<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">
]>
<rss><channel><item><link>&b;</link></item></channel></rss>
"""


class TestExtractLinksRss:
    BASE_URL = "https://atzip.kr/feed/"

    def test_extracts_link_element_and_description_anchors(self, rss_xml):
        content = rss_xml(
            link="https://atzip.kr/2026/07/04/goods-reservation/",
            description_anchors=[
                "https://official-site.com/event?utm_source=atzip&utm_medium=feed",
                "https://atzip.kr/2026/07/04/goods-reservation/",
                "https://twitter.com/example",
                "https://official-site.com/banner.jpg",
            ],
        )

        result = extract_links_rss(content, self.BASE_URL)

        assert result == ["https://official-site.com/event"]

    def test_removes_self_domain_links(self, rss_xml):
        content = rss_xml(
            link="https://atzip.kr/2026/07/04/self/",
            description_anchors=["https://official-site.com/event"],
        )

        result = extract_links_rss(content, self.BASE_URL)

        assert result == ["https://official-site.com/event"]

    def test_self_domain_match_is_exact_hostname_not_subdomain(self, rss_xml):
        content = rss_xml(
            link="https://shop.atzip.kr/goods/1",
            description_anchors=["https://official-site.com/event"],
        )

        result = extract_links_rss(content, self.BASE_URL)

        assert "https://shop.atzip.kr/goods/1" in result

    def test_self_domain_match_is_case_insensitive(self, rss_xml):
        content = rss_xml(
            link="https://ATZIP.KR/2026/07/04/self/",
            description_anchors=["https://official-site.com/event"],
        )

        result = extract_links_rss(content, self.BASE_URL)

        assert result == ["https://official-site.com/event"]

    @pytest.mark.parametrize(
        "sns_url",
        [
            "https://twitter.com/example",
            "https://x.com/example",
            "https://www.instagram.com/example",
        ],
    )
    def test_removes_sns_domain_links(self, sns_url, rss_xml):
        content = rss_xml(description_anchors=["https://official-site.com/event", sns_url])

        result = extract_links_rss(content, self.BASE_URL)

        assert result == ["https://official-site.com/event"]

    @pytest.mark.parametrize(
        "image_url",
        [
            "https://official-site.com/banner.jpg",
            "https://official-site.com/banner.png",
            "https://official-site.com/banner.png?v=2",
        ],
    )
    def test_removes_image_extension_links(self, image_url, rss_xml):
        content = rss_xml(description_anchors=["https://official-site.com/event", image_url])

        result = extract_links_rss(content, self.BASE_URL)

        assert result == ["https://official-site.com/event"]

    def test_strips_tracking_query_params_but_keeps_url(self, rss_xml):
        content = rss_xml(description_anchors=["https://official-site.com/event?utm_source=x&id=1"])

        result = extract_links_rss(content, self.BASE_URL)

        assert result == ["https://official-site.com/event?id=1"]

    @pytest.mark.parametrize("non_http_url", ["mailto:contact@example.com", "javascript:void(0)"])
    def test_removes_non_http_scheme_links(self, non_http_url, rss_xml):
        content = rss_xml(description_anchors=["https://official-site.com/event", non_http_url])

        result = extract_links_rss(content, self.BASE_URL)

        assert result == ["https://official-site.com/event"]

    def test_removes_duplicate_links_preserving_order(self, rss_xml):
        content = rss_xml(
            description_anchors=[
                "https://official-site.com/event-a?utm_source=x",
                "https://official-site.com/event-b",
                "https://official-site.com/event-a?utm_source=y",
            ]
        )

        result = extract_links_rss(content, self.BASE_URL)

        assert result == [
            "https://official-site.com/event-a",
            "https://official-site.com/event-b",
        ]

    def test_no_items_returns_empty_list(self):
        content = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>atzip</title></channel></rss>"""

        result = extract_links_rss(content, self.BASE_URL)

        assert result == []

    def test_accepts_str_with_xml_encoding_declaration(self, rss_xml):
        """§2-4: fetch_html returns a decoded str; a str containing an
        <?xml ... encoding="..."?> declaration must not raise ValueError."""
        content = rss_xml(description_anchors=["https://official-site.com/event"])
        assert content.startswith('<?xml version="1.0" encoding="UTF-8"?>')

        result = extract_links_rss(content, self.BASE_URL)

        assert result == ["https://official-site.com/event"]

    def test_rejects_entity_expansion_payload(self):
        with pytest.raises(DiscoveryParseError):
            extract_links_rss(ENTITY_EXPANSION_XML, self.BASE_URL)

    def test_malformed_xml_raises_discovery_parse_error(self):
        malformed = "<rss><channel><item><link>https://example.com/</item></channel></rss>"

        with pytest.raises(DiscoveryParseError):
            extract_links_rss(malformed, self.BASE_URL)

    def test_encoding_like_text_without_xml_prolog_is_not_mutated(self):
        """§2-4/PR-2 gate fix: the encoding-normalization substitution must
        only touch a real <?xml ... encoding="..." ?> prolog declaration.
        This fixture has no XML prolog at all, so a literal `encoding="x"`
        substring living in ordinary element text (here, inside a <link>
        URL) must survive parsing byte-for-byte instead of being rewritten
        to `encoding="UTF-8"`."""
        content = (
            '<rss version="2.0"><channel><title>atzip</title>'
            '<item><link>https://official-site.com/event?token=encoding="x"</link></item>'
            "</channel></rss>"
        )

        result = extract_links_rss(content, self.BASE_URL)

        assert result == ['https://official-site.com/event?token=encoding%3D%22x%22']

    def test_accepts_content_with_leading_bom(self, rss_xml):
        """Characterization test: aniplus's items.xml RSS feed ships with a
        leading U+FEFF BOM character ahead of the <?xml ... ?> declaration.
        _parse_xml already handles this — the BOM survives the UTF-8
        re-encode as the standard 3-byte UTF-8 BOM sequence, which expat
        (defusedxml's backend) skips transparently."""
        content = "﻿" + rss_xml(description_anchors=["https://official-site.com/event"])

        result = extract_links_rss(content, self.BASE_URL)

        assert result == ["https://official-site.com/event"]

    def test_self_domain_match_ignores_port(self, rss_xml):
        """Characterization test: self-domain matching compares hostname
        only (urlsplit(url).hostname never includes the port), so a
        same-host link on a different port than base_url's is still treated
        as self-domain and removed."""
        content = rss_xml(
            description_anchors=[
                "https://atzip.kr:9443/x",
                "https://official-site.com/event",
            ]
        )

        result = extract_links_rss(content, "https://atzip.kr:8443/feed/")

        assert result == ["https://official-site.com/event"]

    def test_extracts_content_encoded_anchors_and_ignores_self_domain_description(self, rss_xml):
        """Real-source gap (atzip.kr/feed/ smoke): the <description> field
        holds only an excerpt + a self-domain "read more" anchor; the actual
        body HTML with outbound official links lives in <content:encoded>
        (CDATA, xmlns:content namespace). Both fields must be scanned for
        anchors, and the existing filter chain (self-domain, SNS) must still
        apply to whatever content:encoded contains."""
        content = rss_xml(
            link="https://atzip.kr/2026/07/04/goods-reservation/",
            description_anchors=["https://atzip.kr/2026/07/04/goods-reservation/"],
            content_encoded_anchors=[
                "https://official-site.com/event",
                "https://x.com/example",
                "https://www.instagram.com/example",
            ],
        )

        result = extract_links_rss(content, self.BASE_URL)

        assert result == ["https://official-site.com/event"]

    def test_protocol_relative_urls_are_resolved_and_self_domain_still_removed(self, rss_xml):
        """Characterization test: a protocol-relative href ("//host/path")
        resolves against base_url's scheme via urljoin — an official-site
        link survives, but a protocol-relative link back to atzip's own
        domain is still removed by the RSS self-domain rule."""
        content = rss_xml(
            description_anchors=["//official-site.com/event", "//atzip.kr/x"]
        )

        result = extract_links_rss(content, self.BASE_URL)

        assert result == ["https://official-site.com/event"]


class TestExtractLinksSitemap:
    BASE_URL = "https://aniplustv.com/sitemap.xml"

    def test_extracts_loc_elements(self, sitemap_xml):
        content = sitemap_xml(
            "https://aniplustv.com/events/1", "https://aniplustv.com/events/2"
        )

        result = extract_links_sitemap(content, self.BASE_URL)

        assert result == [
            "https://aniplustv.com/events/1",
            "https://aniplustv.com/events/2",
        ]

    def test_keeps_same_domain_links(self, sitemap_xml):
        """Sitemap sources point directly at an official site's own pages —
        the opposite of RSS, which links out from a roundup post."""
        content = sitemap_xml("https://aniplustv.com/events/1")

        result = extract_links_sitemap(content, self.BASE_URL)

        assert result == ["https://aniplustv.com/events/1"]

    @pytest.mark.parametrize(
        "image_url",
        ["https://aniplustv.com/banner.jpg", "https://aniplustv.com/banner.png"],
    )
    def test_removes_image_extension_links(self, image_url, sitemap_xml):
        content = sitemap_xml("https://aniplustv.com/events/1", image_url)

        result = extract_links_sitemap(content, self.BASE_URL)

        assert result == ["https://aniplustv.com/events/1"]

    def test_strips_tracking_query_params_and_dedups(self, sitemap_xml):
        content = sitemap_xml(
            "https://aniplustv.com/events/1",
            "https://aniplustv.com/events/1?utm_source=x",
        )

        result = extract_links_sitemap(content, self.BASE_URL)

        assert result == ["https://aniplustv.com/events/1"]

    def test_no_urls_returns_empty_list(self):
        content = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>"""

        result = extract_links_sitemap(content, self.BASE_URL)

        assert result == []

    def test_accepts_str_with_xml_encoding_declaration(self, sitemap_xml):
        """§2-4: the main smoke-test source (aniplustv sitemap) breaks
        exactly on this path — a str containing an encoding declaration."""
        content = sitemap_xml("https://aniplustv.com/events/1")
        assert content.startswith('<?xml version="1.0" encoding="UTF-8"?>')

        result = extract_links_sitemap(content, self.BASE_URL)

        assert result == ["https://aniplustv.com/events/1"]

    def test_rejects_entity_expansion_payload(self):
        with pytest.raises(DiscoveryParseError):
            extract_links_sitemap(ENTITY_EXPANSION_XML, self.BASE_URL)

    def test_malformed_xml_raises_discovery_parse_error(self):
        malformed = "<urlset><url><loc>https://aniplustv.com/events/1</url></urlset>"

        with pytest.raises(DiscoveryParseError):
            extract_links_sitemap(malformed, self.BASE_URL)

    def test_accepts_content_with_leading_bom(self, sitemap_xml):
        """Characterization test mirroring aniplustv's real items.xml, which
        ships with a leading U+FEFF BOM character (see TestExtractLinksRss's
        equivalent test for why _parse_xml already tolerates this)."""
        content = "﻿" + sitemap_xml("https://aniplustv.com/events/1")

        result = extract_links_sitemap(content, self.BASE_URL)

        assert result == ["https://aniplustv.com/events/1"]

    def test_sorts_by_lastmod_descending(self, sitemap_xml):
        content = sitemap_xml(
            ("https://aniplustv.com/events/1", "2026-01-01"),
            ("https://aniplustv.com/events/2", "2026-07-01"),
            ("https://aniplustv.com/events/3", "2026-03-15"),
        )

        result = extract_links_sitemap(content, self.BASE_URL)

        assert result == [
            "https://aniplustv.com/events/2",
            "https://aniplustv.com/events/3",
            "https://aniplustv.com/events/1",
        ]

    def test_entries_without_lastmod_are_kept_last_in_document_order(self, sitemap_xml):
        content = sitemap_xml(
            ("https://aniplustv.com/events/no-date-a", None),
            ("https://aniplustv.com/events/dated", "2026-07-01"),
            ("https://aniplustv.com/events/no-date-b", None),
        )

        result = extract_links_sitemap(content, self.BASE_URL)

        assert result == [
            "https://aniplustv.com/events/dated",
            "https://aniplustv.com/events/no-date-a",
            "https://aniplustv.com/events/no-date-b",
        ]

    def test_sitemapindex_loc_extraction_is_unaffected_by_lastmod_sort(self):
        """`<sitemapindex>` groups by <sitemap> instead of <url>, but the
        per-group loc+lastmod extraction is tag-name agnostic, so behavior
        here is unchanged from plain loc extraction."""
        content = """<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
<sitemap><loc>https://aniplustv.com/sitemap-events.xml</loc><lastmod>2026-07-01</lastmod></sitemap>
<sitemap><loc>https://aniplustv.com/sitemap-news.xml</loc></sitemap>
</sitemapindex>"""

        result = extract_links_sitemap(content, self.BASE_URL)

        assert result == [
            "https://aniplustv.com/sitemap-events.xml",
            "https://aniplustv.com/sitemap-news.xml",
        ]


class TestExtractLinksHtml:
    BASE_URL = "https://www.animate.co.jp/board/"

    def test_extracts_anchors_matching_selector_with_relative_urls_resolved(self):
        content = """
        <html><body>
        <div class="board-list">
          <a href="/goods/1?utm_source=board">공식 상품 1</a>
          <a href="/goods/1?utm_source=other">공식 상품 1 중복</a>
          <a href="https://twitter.com/example">트위터</a>
          <a href="/banner.jpg">배너</a>
        </div>
        </body></html>
        """

        result = extract_links_html(content, self.BASE_URL, selector=".board-list a")

        assert result == ["https://www.animate.co.jp/goods/1"]

    def test_link_selector_excludes_anchors_outside_scope(self):
        content = """
        <html><body>
        <div class="board-list"><a href="/goods/1">공식 상품 1</a></div>
        <div class="pagination"><a href="/board/?page=2">다음</a></div>
        </body></html>
        """

        result = extract_links_html(content, self.BASE_URL, selector=".board-list a")

        assert result == ["https://www.animate.co.jp/goods/1"]

    def test_keeps_same_domain_links(self):
        content = '<html><body><a href="https://www.animate.co.jp/goods/1">공식 상품 1</a></body></html>'

        result = extract_links_html(content, self.BASE_URL, selector="")

        assert result == ["https://www.animate.co.jp/goods/1"]

    def test_removes_image_extension_links(self):
        content = """
        <html><body>
        <a href="/goods/1">공식 상품 1</a>
        <a href="/banner.png">배너</a>
        </body></html>
        """

        result = extract_links_html(content, self.BASE_URL, selector="")

        assert result == ["https://www.animate.co.jp/goods/1"]

    def test_removes_sns_domain_links(self):
        content = """
        <html><body>
        <a href="/goods/1">공식 상품 1</a>
        <a href="https://www.instagram.com/example">인스타</a>
        </body></html>
        """

        result = extract_links_html(content, self.BASE_URL, selector="")

        assert result == ["https://www.animate.co.jp/goods/1"]

    def test_removes_non_http_scheme_links(self):
        content = """
        <html><body>
        <a href="/goods/1">공식 상품 1</a>
        <a href="mailto:contact@example.com">문의</a>
        </body></html>
        """

        result = extract_links_html(content, self.BASE_URL, selector="")

        assert result == ["https://www.animate.co.jp/goods/1"]

    def test_strips_tracking_query_params_and_dedups(self):
        content = """
        <html><body>
        <a href="/goods/1?utm_source=a">공식 상품 1</a>
        <a href="/goods/1?utm_source=b">공식 상품 1 중복</a>
        </body></html>
        """

        result = extract_links_html(content, self.BASE_URL, selector="")

        assert result == ["https://www.animate.co.jp/goods/1"]

    def test_query_value_spaces_are_reserialized_as_plus(self):
        """Characterization test: stripping tracking params re-serializes the
        surviving query string via urlencode, which normalizes a %20-encoded
        space to "+" — both are valid space encodings in a query string, so
        this is accepted, documented behavior rather than a defect."""
        content = '<html><body><a href="/goods/1?title=a%20b">공식 상품 1</a></body></html>'

        result = extract_links_html(content, self.BASE_URL, selector="")

        assert result == ["https://www.animate.co.jp/goods/1?title=a+b"]

    def test_selector_matching_nothing_returns_empty_list(self):
        content = '<html><body><a href="/goods/1">공식 상품 1</a></body></html>'

        result = extract_links_html(content, self.BASE_URL, selector=".no-such-class a")

        assert result == []

    def test_malformed_html_returns_empty_list_not_raises(self):
        malformed = "<html><body><a href='unclosed<div><p>broken"

        result = extract_links_html(malformed, self.BASE_URL, selector="")

        assert result == []

    def test_self_referencing_anchors_are_excluded(self):
        """A bare href="" or a same-page href="#top" resolves to the listing
        page itself (fragment-only navigation), never a distinct candidate
        event page — this must be excluded even though html sources keep
        same-domain links (remove_self_domain=False)."""
        content = """
        <html><body>
        <a href="">빈 링크</a>
        <a href="#top">맨 위로</a>
        <a href="/goods/1">공식 상품 1</a>
        </body></html>
        """

        result = extract_links_html(content, self.BASE_URL, selector="")

        assert result == ["https://www.animate.co.jp/goods/1"]

    def test_invalid_selector_raises_discovery_parse_error(self):
        """A malformed `link_selector` (soupsieve SelectorSyntaxError) must
        surface as DiscoveryParseError rather than a silent empty result —
        an empty result here looks identical to "no links on the page today"
        and would hide a permanently broken selector from PR-3's last_error
        reporting."""
        content = '<html><body><a href="/goods/1">공식 상품 1</a></body></html>'

        with pytest.raises(DiscoveryParseError):
            extract_links_html(content, self.BASE_URL, selector="[[[")

    def test_blank_selector_matches_all_anchors_in_document(self):
        content = """
        <html><body>
        <a href="/goods/1">공식 상품 1</a>
        <a href="/goods/2">공식 상품 2</a>
        </body></html>
        """

        result = extract_links_html(content, self.BASE_URL, selector="")

        assert result == [
            "https://www.animate.co.jp/goods/1",
            "https://www.animate.co.jp/goods/2",
        ]


class TestExtractCandidateUrls:
    def test_dispatches_rss_source_type(self, rss_xml):
        content = rss_xml(description_anchors=["https://official-site.com/event"])

        result = extract_candidate_urls("rss", content, "https://atzip.kr/feed/")

        assert result == ["https://official-site.com/event"]

    def test_dispatches_sitemap_source_type(self, sitemap_xml):
        content = sitemap_xml("https://aniplustv.com/events/1")

        result = extract_candidate_urls("sitemap", content, "https://aniplustv.com/sitemap.xml")

        assert result == ["https://aniplustv.com/events/1"]

    def test_dispatches_html_with_selector(self):
        content = '<html><body><div class="board-list"><a href="/goods/1">공식 상품 1</a></div></body></html>'

        result = extract_candidate_urls(
            "html",
            content,
            "https://www.animate.co.jp/board/",
            selector=".board-list a",
        )

        assert result == ["https://www.animate.co.jp/goods/1"]

    def test_html_without_selector_argument_defaults_to_blank_string(self):
        content = '<html><body><a href="/goods/1">공식 상품 1</a></body></html>'

        result = extract_candidate_urls("html", content, "https://www.animate.co.jp/board/")

        assert result == ["https://www.animate.co.jp/goods/1"]

    def test_unknown_source_type_raises_value_error(self):
        with pytest.raises(ValueError):
            extract_candidate_urls("atom", "<xml/>", "https://example.com/")
