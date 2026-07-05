"""Pure link-extraction functions for the draft auto-discovery pipeline
(prompt_plan.md §2-1). No DB access, no network I/O — callers (the future
`discover_drafts` command, PR-3) are responsible for fetching `content` via
`drafts.fetching.fetch_html` and persisting anything.

XML parsing safety (§2-4): raw RSS/sitemap XML is untrusted input, so it is
parsed with `defusedxml` rather than `xml.etree.ElementTree` directly —
`xml.etree.ElementTree` performs unbounded entity expansion ("billion
laughs"), which a response-size cap alone does not stop (a few KB of markup
can expand to gigabytes in memory). `fetch_html` also returns an already
decoded `str`, so an `<?xml ... encoding="...">` declaration in that str
would raise `ValueError` if handed to `fromstring` unchanged — `_parse_xml`
neutralizes the declared encoding and re-encodes to UTF-8 bytes before
parsing to avoid that mismatch.
"""
import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from defusedxml.ElementTree import ParseError, fromstring
from defusedxml.common import DefusedXmlException
from soupsieve.util import SelectorSyntaxError


class DiscoveryParseError(Exception):
    """Raised when RSS/sitemap XML content cannot be safely parsed —
    malformed markup or an entity-expansion payload (see module docstring).
    """


# SNS domains that are never event sources in their own right (§ PO decision
# 5): only these exact hosts (+ their www. variant) are enforced by tests.
_SNS_HOSTNAMES = {
    "x.com",
    "www.x.com",
    "twitter.com",
    "www.twitter.com",
    "instagram.com",
    "www.instagram.com",
}

_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg")

_XML_ENCODING_DECLARATION = re.compile(r'encoding=["\'][^"\']*["\']')
# The XML prolog must be the very first thing in a document (a leading BOM
# is the only thing allowed before it per the XML spec), so anchoring here
# also keeps the encoding substitution below from ever touching ordinary
# element/attribute text elsewhere in the document that happens to contain
# the literal substring `encoding="..."`.
_XML_PROLOG = re.compile(r'\A﻿?<\?xml\b[^>]*\?>')


def _parse_xml(content):
    # Force the declared encoding to match the UTF-8 bytes this function
    # encodes `content` into — `content` is already a decoded Python str
    # (fetch_html's return type), so whatever encoding the original response
    # declared no longer applies to it. Only the prolog itself is rewritten;
    # a document with no <?xml ... ?> declaration is passed through as-is.
    prolog_match = _XML_PROLOG.match(content)
    if prolog_match:
        prolog = prolog_match.group()
        normalized_prolog = _XML_ENCODING_DECLARATION.sub('encoding="UTF-8"', prolog, count=1)
        normalized = normalized_prolog + content[prolog_match.end():]
    else:
        normalized = content
    try:
        return fromstring(normalized.encode("utf-8"))
    except (ParseError, DefusedXmlException) as exc:
        raise DiscoveryParseError(str(exc)) from exc


def _is_http_url(url):
    return urlsplit(url).scheme in ("http", "https")


def _is_image_url(url):
    return urlsplit(url).path.lower().endswith(_IMAGE_EXTENSIONS)


def _is_sns_url(url):
    hostname = urlsplit(url).hostname
    return hostname is not None and hostname in _SNS_HOSTNAMES


def _matches_hostname(url, hostname):
    return hostname is not None and urlsplit(url).hostname == hostname


def _strip_tracking_params(url):
    # Re-serializing the surviving params via urlencode normalizes encoding
    # along the way (e.g. a %20-encoded space becomes "+") — both are valid
    # space encodings in a query string, so this is intended, not a defect.
    parts = urlsplit(url)
    kept_params = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.startswith("utm_")
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(kept_params), parts.fragment))


def _matches_base_page(cleaned_url, self_page):
    # Fragment-only navigation (href="#top") or a bare href="" resolves back
    # to the listing page itself, never a distinct candidate event page —
    # compared with the fragment ignored on both sides, after the same
    # tracking-param stripping applied to `cleaned_url`.
    return urlsplit(cleaned_url)._replace(fragment="") == self_page


def _filter_and_dedupe(raw_urls, base_url, *, remove_self_domain):
    self_hostname = urlsplit(base_url).hostname if remove_self_domain else None
    self_page = urlsplit(_strip_tracking_params(base_url))._replace(fragment="")
    seen = set()
    result = []
    for raw_url in raw_urls:
        url = urljoin(base_url, raw_url)
        if not _is_http_url(url):
            continue
        if _is_image_url(url):
            continue
        if _is_sns_url(url):
            continue
        if remove_self_domain and _matches_hostname(url, self_hostname):
            continue
        cleaned_url = _strip_tracking_params(url)
        if _matches_base_page(cleaned_url, self_page):
            continue
        if cleaned_url in seen:
            continue
        seen.add(cleaned_url)
        result.append(cleaned_url)
    return result


def extract_links_rss(content, base_url):
    """Extract candidate event-page URLs from a WordPress-style RSS feed
    (atzip's roundup posts): each <item>'s own <link> plus every <a href>
    found inside its <description> and <content:encoded> CDATA blocks.
    Real WordPress feeds (atzip.kr/feed/) put only an excerpt + a
    self-domain "read more" anchor in <description>; the actual post body
    HTML — where the outbound official links live — is in
    <content:encoded> (the http://purl.org/rss/1.0/modules/content/
    namespace), so both fields must be scanned or the feed yields zero
    candidates. Matched by local tag name (`_local_tag`, shared with the
    sitemap extractor) so the xmlns:content prefix binding doesn't need
    explicit handling. Self-domain links are removed — an RSS roundup links
    *out* to official sources, so the feed's own permalink is never itself a
    candidate event page (unlike sitemap/html sources, which point directly
    at an official site's own pages)."""
    root = _parse_xml(content)
    candidates = []
    channel = root.find("channel")
    items = channel.findall("item") if channel is not None else []
    for item in items:
        link = item.find("link")
        if link is not None and link.text:
            candidates.append(link.text.strip())
        for tag_name in ("description", "encoded"):
            html_element = _first_local_child(item, tag_name)
            if html_element is not None and html_element.text:
                soup = BeautifulSoup(html_element.text, "html.parser")
                candidates.extend(a["href"] for a in soup.find_all("a", href=True))
    return _filter_and_dedupe(candidates, base_url, remove_self_domain=True)


def _local_tag(tag):
    return tag.rsplit("}", 1)[-1]


def _first_local_child(element, tag_name):
    return next(
        (child for child in element if _local_tag(child.tag) == tag_name), None
    )


def extract_links_sitemap(content, base_url):
    """Extract every <loc> URL from a sitemap.xml (namespace-agnostic —
    matched by local tag name so the sitemaps.org xmlns declaration doesn't
    need explicit handling), one per <url> (or <sitemap>, for a
    <sitemapindex>) group, alongside that group's own <lastmod> sibling.
    Entries are returned newest-first by <lastmod> (ISO date strings sort
    correctly as plain strings); entries with no <lastmod> keep their
    original document order at the end, since there is nothing to rank them
    by. Same-domain links are kept: a sitemap points directly at an official
    site's own pages, unlike an RSS roundup."""
    root = _parse_xml(content)
    entries = []
    for group in root:
        loc_element = _first_local_child(group, "loc")
        if loc_element is None or not loc_element.text:
            continue
        lastmod_element = _first_local_child(group, "lastmod")
        lastmod = (
            lastmod_element.text.strip()
            if lastmod_element is not None and lastmod_element.text
            else None
        )
        entries.append((loc_element.text.strip(), lastmod))

    dated = sorted((e for e in entries if e[1] is not None), key=lambda e: e[1], reverse=True)
    undated = [e for e in entries if e[1] is None]
    candidates = [loc for loc, _ in dated + undated]
    return _filter_and_dedupe(candidates, base_url, remove_self_domain=False)


def extract_links_html(content, base_url, selector=""):
    """Extract <a href> URLs from an HTML board/listing page. `selector` is a
    CSS selector scoping which anchors count (e.g. ".board-list a" for
    animate); a blank selector matches every anchor in the document.
    Malformed HTML never raises — BeautifulSoup's html.parser is a lenient
    parser by design, so worst case is an empty result, not an exception.
    A malformed `selector` is different: soupsieve raises SelectorSyntaxError
    for it, which is re-raised as DiscoveryParseError rather than swallowed —
    a silently empty result here would look identical to "no links today"
    and hide a permanently broken link_selector from operators."""
    soup = BeautifulSoup(content, "html.parser")
    try:
        anchors = soup.select(selector) if selector else soup.find_all("a")
    except SelectorSyntaxError as exc:
        raise DiscoveryParseError(str(exc)) from exc
    candidates = [anchor["href"] for anchor in anchors if anchor.has_attr("href")]
    return _filter_and_dedupe(candidates, base_url, remove_self_domain=False)


_EXTRACTORS = {
    "rss": lambda content, base_url, selector: extract_links_rss(content, base_url),
    "sitemap": lambda content, base_url, selector: extract_links_sitemap(content, base_url),
    "html": extract_links_html,
}


def extract_candidate_urls(source_type, content, base_url, selector=""):
    try:
        extractor = _EXTRACTORS[source_type]
    except KeyError:
        raise ValueError(f"Unknown source_type: {source_type!r}") from None
    return extractor(content, base_url, selector)
