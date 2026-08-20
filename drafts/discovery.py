"""RSS/사이트맵/HTML에서 후보 URL만 뽑는 순수 함수 모음(DB 접근·네트워크 I/O 없음).
`content`를 실제로 가져오고 저장하는 일은 호출자 몫이다.

XML은 표준 xml.etree 대신 defusedxml로 파싱한다 — 외부에서 받은 RSS/사이트맵 XML은
신뢰할 수 없는 입력이라, xml.etree로 그대로 파싱하면 엔티티 확장("billion laughs") 공격에
노출되고 응답 크기 제한만으로는 막을 수 없다(몇 KB짜리 마크업이 메모리에서 기가바이트로
불어날 수 있다). `content`는 이미 디코딩된 문자열이라, 그 안의 `<?xml ... encoding="...">`
선언을 그대로 두고 fromstring에 넘기면 ValueError가 나므로 `_parse_xml`이 선언을 UTF-8로
맞춰 재인코딩한 뒤 파싱한다.
"""
import re
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup
from defusedxml.ElementTree import ParseError, fromstring
from defusedxml.common import DefusedXmlException
from soupsieve.util import SelectorSyntaxError


class DiscoveryParseError(Exception):
    """RSS/사이트맵 XML을 안전하게 파싱할 수 없을 때 발생한다 —
    잘못된 마크업이거나 엔티티 확장 공격 페이로드다."""


# SNS 도메인은 행사 출처가 될 수 없다. www. 변형 포함, 정확히 나열된 호스트만 대상이다.
_SNS_HOSTNAMES = {
    "x.com",
    "www.x.com",
    "twitter.com",
    "www.twitter.com",
    "instagram.com",
    "www.instagram.com",
}
# 러너 API가 제외 호스트 목록을 노출할 때 쓰는 공개 별칭 — 사설 이름을 밖에서 직접 임포트하지 않게 한다.
SNS_HOSTNAMES = _SNS_HOSTNAMES

_IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg")

_XML_ENCODING_DECLARATION = re.compile(r'encoding=["\'][^"\']*["\']')
# XML 프롤로그는 문서 맨 앞(BOM 제외)에만 올 수 있어, 정규식을 앞쪽에 고정하면 본문에
# 우연히 등장하는 encoding="..." 문자열까지 잘못 치환되는 일이 없다.
_XML_PROLOG = re.compile(r'\A﻿?<\?xml\b[^>]*\?>')


def _parse_xml(content):
    # content는 이미 디코딩된 문자열이라 원래 인코딩 선언이 더는 유효하지 않으므로,
    # UTF-8로 다시 인코딩하기 전에 프롤로그의 선언만 맞춰 고친다. <?xml ...?> 선언이
    # 없는 문서는 그대로 둔다.
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
    # urlencode로 다시 조립하면 %20이 +로 바뀌는 등 인코딩이 달라질 수 있는데,
    # 둘 다 유효한 표현이라 의도된 동작이다.
    parts = urlsplit(url)
    kept_params = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.startswith("utm_")
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(kept_params), parts.fragment))


def _matches_base_page(cleaned_url, self_page):
    # href="#top"처럼 프래그먼트만 있거나 href=""인 링크는 목록 페이지 자신을 가리킬
    # 뿐 별도 후보가 아니므로, 양쪽 다 프래그먼트를 제거하고 비교한다.
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
    """WordPress 스타일 RSS(atzip 취합글)에서 후보 URL을 뽑는다: 각 item의 <link>와
    <description>/<content:encoded> 안의 모든 <a href>. 실제 본문 링크는
    <content:encoded>에만 있는 경우가 많아 두 필드를 다 봐야 한다. RSS 취합글은 외부
    공식 링크로 나가는 성격이라 피드 자신의 permalink(자기 도메인)는 후보에서 제외한다."""
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
    """사이트맵 XML에서 <loc> URL을 전부 뽑는다(네임스페이스 무관하게 로컬 태그명으로
    매칭). <lastmod> 기준 최신순으로 정렬하고, <lastmod>가 없는 항목은 원래 순서
    그대로 맨 뒤에 둔다. 사이트맵은 공식 사이트 자신의 페이지를 직접 가리키므로 자기
    도메인 링크도 그대로 남긴다."""
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
    """HTML 목록/게시판 페이지에서 <a href>를 추출한다. selector는 어떤 앵커를 포함할지
    좁히는 CSS 선택자이고(예: animate의 ".board-list a"), 비어 있으면 문서의 모든
    앵커를 본다. BeautifulSoup의 html.parser는 관대해서 마크업이 깨져도 예외 없이 빈
    결과만 낸다. 다만 selector 자체가 잘못되면 soupsieve가 예외를 내는데, 이를 삼키면
    "오늘은 링크가 없다"와 구분이 안 되므로 DiscoveryParseError로 다시 던져 운영자가
    알 수 있게 한다."""
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
