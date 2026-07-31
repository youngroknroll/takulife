"""drafts.discovery(자동 발견 파이프라인의 순수 링크 추출 함수) 테스트. DB·네트워크
없이 문자열 fixture만 쓴다. XML fixture에 encoding 선언을 넣는 이유는 fetch_html이
이미 디코딩한 str을 그대로 흉내 내기 위해서다 — 이 경우 xml.etree의 단순
fromstring(str) 호출이 깨진다."""
import pytest

from drafts.discovery import (
    DiscoveryParseError,
    extract_candidate_urls,
    extract_links_html,
    extract_links_rss,
    extract_links_sitemap,
)


# billion-laughs류 엔티티 확장 공격 페이로드를 축소한 것. defusedxml은 크기와
# 무관하게 이 형태 자체를 거부해야 한다.
ENTITY_EXPANSION_XML = """<?xml version="1.0"?>
<!DOCTYPE rss [
<!ENTITY a "spam">
<!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">
]>
<rss><channel><item><link>&b;</link></item></channel></rss>
"""


pytestmark = pytest.mark.unit


class TestExtractLinksRss:
    BASE_URL = "https://atzip.kr/feed/"

    def test_RSS_link_요소와_description_앵커에서_외부_링크를_추출한다(self, rss_xml):
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

    def test_RSS에서_자기_도메인_링크는_제거된다(self, rss_xml):
        content = rss_xml(
            link="https://atzip.kr/2026/07/04/self/",
            description_anchors=["https://official-site.com/event"],
        )

        result = extract_links_rss(content, self.BASE_URL)

        assert result == ["https://official-site.com/event"]

    def test_RSS_자기_도메인_판정은_서브도메인이_아닌_정확한_호스트명만_일치한다(self, rss_xml):
        content = rss_xml(
            link="https://shop.atzip.kr/goods/1",
            description_anchors=["https://official-site.com/event"],
        )

        result = extract_links_rss(content, self.BASE_URL)

        assert "https://shop.atzip.kr/goods/1" in result

    def test_RSS_자기_도메인_판정은_대소문자를_구분하지_않는다(self, rss_xml):
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
        ids=["트위터", "X닷컴", "인스타그램"],
    )
    def test_RSS에서_SNS_도메인_링크는_제거된다(self, sns_url, rss_xml):
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
        ids=["jpg", "png", "쿼리있는_png"],
    )
    def test_RSS에서_이미지_확장자_링크는_제거된다(self, image_url, rss_xml):
        content = rss_xml(description_anchors=["https://official-site.com/event", image_url])

        result = extract_links_rss(content, self.BASE_URL)

        assert result == ["https://official-site.com/event"]

    def test_RSS에서_추적_쿼리_파라미터는_제거하고_URL은_유지한다(self, rss_xml):
        content = rss_xml(description_anchors=["https://official-site.com/event?utm_source=x&id=1"])

        result = extract_links_rss(content, self.BASE_URL)

        assert result == ["https://official-site.com/event?id=1"]

    @pytest.mark.parametrize(
        "non_http_url",
        ["mailto:contact@example.com", "javascript:void(0)"],
        ids=["mailto", "javascript"],
    )
    def test_RSS에서_http가_아닌_스킴_링크는_제거된다(self, non_http_url, rss_xml):
        content = rss_xml(description_anchors=["https://official-site.com/event", non_http_url])

        result = extract_links_rss(content, self.BASE_URL)

        assert result == ["https://official-site.com/event"]

    def test_RSS에서_중복_링크는_순서를_보존하며_제거된다(self, rss_xml):
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

    def test_RSS에_아이템이_없으면_빈_목록을_반환한다(self):
        content = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>atzip</title></channel></rss>"""

        result = extract_links_rss(content, self.BASE_URL)

        assert result == []

    def test_RSS는_encoding_선언이_있는_문자열도_파싱한다(self, rss_xml):
        """fetch_html은 이미 디코딩된 str을 반환하므로, encoding 선언이 들어있는
        문자열이어도 ValueError 없이 파싱돼야 한다."""
        content = rss_xml(description_anchors=["https://official-site.com/event"])
        assert content.startswith('<?xml version="1.0" encoding="UTF-8"?>')

        result = extract_links_rss(content, self.BASE_URL)

        assert result == ["https://official-site.com/event"]

    def test_RSS는_엔티티_확장_공격_페이로드를_거부한다(self):
        with pytest.raises(DiscoveryParseError):
            extract_links_rss(ENTITY_EXPANSION_XML, self.BASE_URL)

    def test_RSS_XML이_손상되면_DiscoveryParseError를_발생시킨다(self):
        malformed = "<rss><channel><item><link>https://example.com/</item></channel></rss>"

        with pytest.raises(DiscoveryParseError):
            extract_links_rss(malformed, self.BASE_URL)

    def test_XML_prolog가_없으면_본문_속의_encoding_유사_문자열이_변형되지_않는다(self):
        """encoding 정규화 치환은 실제 <?xml ... encoding="..." ?> 선언부만
        건드려야 한다. 이 fixture는 XML prolog가 없으므로 본문 텍스트(링크 URL)
        속 "encoding=" 문자열이 잘못 치환되지 않고 그대로 살아남아야 한다."""
        content = (
            '<rss version="2.0"><channel><title>atzip</title>'
            '<item><link>https://official-site.com/event?token=encoding="x"</link></item>'
            "</channel></rss>"
        )

        result = extract_links_rss(content, self.BASE_URL)

        assert result == ['https://official-site.com/event?token=encoding%3D%22x%22']

    def test_RSS는_선행_BOM이_있어도_파싱한다(self, rss_xml):
        """aniplus의 실제 items.xml RSS 피드는 <?xml ...?> 선언 앞에 BOM 문자가
        붙어 온다. _parse_xml이 이미 이를 처리하므로 파싱이 정상 동작해야 한다."""
        content = "﻿" + rss_xml(description_anchors=["https://official-site.com/event"])

        result = extract_links_rss(content, self.BASE_URL)

        assert result == ["https://official-site.com/event"]

    def test_RSS_자기_도메인_판정은_포트를_무시한다(self, rss_xml):
        """자기 도메인 판정은 호스트명만 비교하므로(포트 미포함) base_url과
        포트가 달라도 같은 호스트면 자기 도메인으로 제거돼야 한다."""
        content = rss_xml(
            description_anchors=[
                "https://atzip.kr:9443/x",
                "https://official-site.com/event",
            ]
        )

        result = extract_links_rss(content, "https://atzip.kr:8443/feed/")

        assert result == ["https://official-site.com/event"]

    def test_RSS는_content_encoded_앵커도_추출하고_자기_도메인_필터를_동일하게_적용한다(self, rss_xml):
        """atzip.kr/feed/의 실제 구조: <description>은 발췌만 담고, 외부 공식
        링크가 있는 실제 본문 HTML은 <content:encoded>에 있다. 두 필드 모두
        앵커를 스캔하고 기존 필터(자기 도메인, SNS)를 동일하게 적용해야 한다."""
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

    def test_RSS는_프로토콜_상대_URL을_해석하고_자기_도메인은_계속_제거한다(self, rss_xml):
        """프로토콜 상대 href("//host/path")는 base_url의 스킴으로 해석된다.
        공식 사이트 링크는 남고, atzip 자기 도메인으로 가는 링크는 여전히
        제거돼야 한다."""
        content = rss_xml(
            description_anchors=["//official-site.com/event", "//atzip.kr/x"]
        )

        result = extract_links_rss(content, self.BASE_URL)

        assert result == ["https://official-site.com/event"]


class TestExtractLinksSitemap:
    BASE_URL = "https://aniplustv.com/sitemap.xml"

    def test_사이트맵_loc_요소를_추출한다(self, sitemap_xml):
        content = sitemap_xml(
            "https://aniplustv.com/events/1", "https://aniplustv.com/events/2"
        )

        result = extract_links_sitemap(content, self.BASE_URL)

        assert result == [
            "https://aniplustv.com/events/1",
            "https://aniplustv.com/events/2",
        ]

    def test_사이트맵은_같은_도메인_링크를_유지한다(self, sitemap_xml):
        """사이트맵 소스는 RSS(외부로 링크하는 정리글)와 반대로 공식 사이트
        자신의 페이지를 직접 가리킨다."""
        content = sitemap_xml("https://aniplustv.com/events/1")

        result = extract_links_sitemap(content, self.BASE_URL)

        assert result == ["https://aniplustv.com/events/1"]

    @pytest.mark.parametrize(
        "image_url",
        ["https://aniplustv.com/banner.jpg", "https://aniplustv.com/banner.png"],
        ids=["jpg", "png"],
    )
    def test_사이트맵에서_이미지_확장자_링크는_제거된다(self, image_url, sitemap_xml):
        content = sitemap_xml("https://aniplustv.com/events/1", image_url)

        result = extract_links_sitemap(content, self.BASE_URL)

        assert result == ["https://aniplustv.com/events/1"]

    def test_사이트맵에서_추적_쿼리_파라미터를_제거하고_중복을_제거한다(self, sitemap_xml):
        content = sitemap_xml(
            "https://aniplustv.com/events/1",
            "https://aniplustv.com/events/1?utm_source=x",
        )

        result = extract_links_sitemap(content, self.BASE_URL)

        assert result == ["https://aniplustv.com/events/1"]

    def test_사이트맵에_URL이_없으면_빈_목록을_반환한다(self):
        content = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"></urlset>"""

        result = extract_links_sitemap(content, self.BASE_URL)

        assert result == []

    def test_사이트맵은_encoding_선언이_있는_문자열도_파싱한다(self, sitemap_xml):
        """실제 스모크 테스트 대상인 aniplustv 사이트맵이 바로 이 경로(encoding
        선언이 포함된 문자열)에서 깨졌었다."""
        content = sitemap_xml("https://aniplustv.com/events/1")
        assert content.startswith('<?xml version="1.0" encoding="UTF-8"?>')

        result = extract_links_sitemap(content, self.BASE_URL)

        assert result == ["https://aniplustv.com/events/1"]

    def test_사이트맵은_엔티티_확장_공격_페이로드를_거부한다(self):
        with pytest.raises(DiscoveryParseError):
            extract_links_sitemap(ENTITY_EXPANSION_XML, self.BASE_URL)

    def test_사이트맵_XML이_손상되면_DiscoveryParseError를_발생시킨다(self):
        malformed = "<urlset><url><loc>https://aniplustv.com/events/1</url></urlset>"

        with pytest.raises(DiscoveryParseError):
            extract_links_sitemap(malformed, self.BASE_URL)

    def test_사이트맵은_선행_BOM이_있어도_파싱한다(self, sitemap_xml):
        """aniplustv의 실제 items.xml처럼 선행 BOM 문자가 있어도 파싱돼야 한다."""
        content = "﻿" + sitemap_xml("https://aniplustv.com/events/1")

        result = extract_links_sitemap(content, self.BASE_URL)

        assert result == ["https://aniplustv.com/events/1"]

    def test_사이트맵_URL은_lastmod_내림차순으로_정렬된다(self, sitemap_xml):
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

    def test_lastmod이_없는_URL은_문서_순서대로_맨_뒤에_유지된다(self, sitemap_xml):
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

    def test_sitemapindex의_loc_추출도_lastmod_정렬_규칙을_동일하게_따른다(self):
        """<sitemapindex>는 <url> 대신 <sitemap>으로 묶이지만 loc+lastmod
        추출은 태그명과 무관하므로 일반 loc 추출과 동일하게 동작한다."""
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

    def test_HTML은_셀렉터에_일치하는_앵커의_상대_URL을_절대_URL로_해석한다(self):
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

    def test_HTML_링크_셀렉터는_범위_밖_앵커를_제외한다(self):
        content = """
        <html><body>
        <div class="board-list"><a href="/goods/1">공식 상품 1</a></div>
        <div class="pagination"><a href="/board/?page=2">다음</a></div>
        </body></html>
        """

        result = extract_links_html(content, self.BASE_URL, selector=".board-list a")

        assert result == ["https://www.animate.co.jp/goods/1"]

    def test_HTML은_같은_도메인_링크를_유지한다(self):
        content = '<html><body><a href="https://www.animate.co.jp/goods/1">공식 상품 1</a></body></html>'

        result = extract_links_html(content, self.BASE_URL, selector="")

        assert result == ["https://www.animate.co.jp/goods/1"]

    def test_HTML에서_이미지_확장자_링크는_제거된다(self):
        content = """
        <html><body>
        <a href="/goods/1">공식 상품 1</a>
        <a href="/banner.png">배너</a>
        </body></html>
        """

        result = extract_links_html(content, self.BASE_URL, selector="")

        assert result == ["https://www.animate.co.jp/goods/1"]

    def test_HTML에서_SNS_도메인_링크는_제거된다(self):
        content = """
        <html><body>
        <a href="/goods/1">공식 상품 1</a>
        <a href="https://www.instagram.com/example">인스타</a>
        </body></html>
        """

        result = extract_links_html(content, self.BASE_URL, selector="")

        assert result == ["https://www.animate.co.jp/goods/1"]

    def test_HTML에서_http가_아닌_스킴_링크는_제거된다(self):
        content = """
        <html><body>
        <a href="/goods/1">공식 상품 1</a>
        <a href="mailto:contact@example.com">문의</a>
        </body></html>
        """

        result = extract_links_html(content, self.BASE_URL, selector="")

        assert result == ["https://www.animate.co.jp/goods/1"]

    def test_HTML에서_추적_쿼리_파라미터를_제거하고_중복을_제거한다(self):
        content = """
        <html><body>
        <a href="/goods/1?utm_source=a">공식 상품 1</a>
        <a href="/goods/1?utm_source=b">공식 상품 1 중복</a>
        </body></html>
        """

        result = extract_links_html(content, self.BASE_URL, selector="")

        assert result == ["https://www.animate.co.jp/goods/1"]

    def test_HTML_쿼리_값의_공백은_plus_기호로_재직렬화된다(self):
        """추적 파라미터 제거 후 남은 쿼리를 urlencode로 재직렬화하면 %20이
        "+"로 바뀐다. 둘 다 유효한 공백 인코딩이라 결함이 아니라 의도된 동작이다."""
        content = '<html><body><a href="/goods/1?title=a%20b">공식 상품 1</a></body></html>'

        result = extract_links_html(content, self.BASE_URL, selector="")

        assert result == ["https://www.animate.co.jp/goods/1?title=a+b"]

    def test_HTML_셀렉터가_아무것도_찾지_못하면_빈_목록을_반환한다(self):
        content = '<html><body><a href="/goods/1">공식 상품 1</a></body></html>'

        result = extract_links_html(content, self.BASE_URL, selector=".no-such-class a")

        assert result == []

    def test_손상된_HTML은_예외_대신_빈_목록을_반환한다(self):
        malformed = "<html><body><a href='unclosed<div><p>broken"

        result = extract_links_html(malformed, self.BASE_URL, selector="")

        assert result == []

    def test_HTML에서_자기_참조_앵커는_제외된다(self):
        """href=""나 href="#top"은 목록 페이지 자신을 가리킬 뿐 별개의 후보
        페이지가 아니다. html 소스가 같은 도메인 링크를 남기더라도 이런
        자기 참조 앵커는 제외해야 한다."""
        content = """
        <html><body>
        <a href="">빈 링크</a>
        <a href="#top">맨 위로</a>
        <a href="/goods/1">공식 상품 1</a>
        </body></html>
        """

        result = extract_links_html(content, self.BASE_URL, selector="")

        assert result == ["https://www.animate.co.jp/goods/1"]

    def test_HTML_셀렉터_문법이_잘못되면_DiscoveryParseError를_발생시킨다(self):
        """잘못된 link_selector는 빈 결과가 아니라 DiscoveryParseError로
        드러나야 한다. 빈 결과는 "오늘은 링크가 없음"과 구분이 안 되어
        영구히 고장난 셀렉터를 운영 화면(last_error)에서 숨겨버린다."""
        content = '<html><body><a href="/goods/1">공식 상품 1</a></body></html>'

        with pytest.raises(DiscoveryParseError):
            extract_links_html(content, self.BASE_URL, selector="[[[")

    def test_빈_셀렉터는_문서의_모든_앵커에_매칭한다(self):
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
    def test_소스_타입이_rss면_RSS_추출_로직으로_디스패치한다(self, rss_xml):
        content = rss_xml(description_anchors=["https://official-site.com/event"])

        result = extract_candidate_urls("rss", content, "https://atzip.kr/feed/")

        assert result == ["https://official-site.com/event"]

    def test_소스_타입이_sitemap이면_사이트맵_추출_로직으로_디스패치한다(self, sitemap_xml):
        content = sitemap_xml("https://aniplustv.com/events/1")

        result = extract_candidate_urls("sitemap", content, "https://aniplustv.com/sitemap.xml")

        assert result == ["https://aniplustv.com/events/1"]

    def test_소스_타입이_html이면_셀렉터와_함께_HTML_추출_로직으로_디스패치한다(self):
        content = '<html><body><div class="board-list"><a href="/goods/1">공식 상품 1</a></div></body></html>'

        result = extract_candidate_urls(
            "html",
            content,
            "https://www.animate.co.jp/board/",
            selector=".board-list a",
        )

        assert result == ["https://www.animate.co.jp/goods/1"]

    def test_HTML_추출에서_셀렉터_인자를_생략하면_빈_문자열로_기본_처리된다(self):
        content = '<html><body><a href="/goods/1">공식 상품 1</a></body></html>'

        result = extract_candidate_urls("html", content, "https://www.animate.co.jp/board/")

        assert result == ["https://www.animate.co.jp/goods/1"]

    def test_알_수_없는_소스_타입은_ValueError를_발생시킨다(self):
        with pytest.raises(ValueError):
            extract_candidate_urls("atom", "<xml/>", "https://example.com/")
