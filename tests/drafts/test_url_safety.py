"""drafts.url_safety(드래프트 fetch URL의 SSRF 방어) 단위 테스트. 스킴·호스트명
거부, 리터럴 IP 사설망 차단, DNS 리졸버 경로를 다룬다."""
import pytest

from drafts.url_safety import (
    InvalidFetchUrlError,
    UnsafeFetchUrlError,
    validate_fetch_url,
)

pytestmark = pytest.mark.unit


class TestSchemeAndHost:
    @pytest.mark.parametrize(
        "url",
        ["ftp://example.com", "file:///etc/passwd", "javascript:alert(1)"],
        ids=["ftp_스킴", "file_스킴", "javascript_스킴"],
    )
    def test_http_https가_아닌_스킴은_거부된다(self, url):
        with pytest.raises(InvalidFetchUrlError):
            validate_fetch_url(url)

    def test_호스트명이_없는_URL은_거부된다(self):
        with pytest.raises(InvalidFetchUrlError):
            validate_fetch_url("http:///path-only")

    def test_localhost는_거부된다(self):
        with pytest.raises(UnsafeFetchUrlError):
            validate_fetch_url("http://localhost/page")


class TestLiteralIp:
    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1/",
            "http://10.0.0.5/",
            "http://192.168.1.1/",
            "http://169.254.169.254/latest/meta-data/",  # 클라우드 메타데이터 주소
            "http://[::1]/",
            "http://0.0.0.0/",
            "http://[::ffff:127.0.0.1]/",
            "http://[::ffff:169.254.169.254]/",
            "http://0.1.2.3/",
        ],
        ids=[
            "루프백_127",
            "사설망_10대",
            "사설망_192대",
            "클라우드_메타데이터_주소",
            "IPv6_루프백",
            "모든_주소_0000",
            "IPv4_매핑_루프백",
            "IPv4_매핑_클라우드_메타데이터_주소",
            "0_0_0_0_8_하위_주소",
        ],
    )
    def test_사설_또는_특수_리터럴_IP는_거부된다(self, url):
        with pytest.raises(UnsafeFetchUrlError):
            validate_fetch_url(url)

    def test_공인_리터럴_IP는_그_IP_문자열을_반환한다(self):
        assert validate_fetch_url("http://8.8.8.8/") == "8.8.8.8"


class TestResolverPath:
    def test_사설_IP로_해석되는_호스트명은_거부된다(self, fake_resolver):
        with pytest.raises(UnsafeFetchUrlError):
            validate_fetch_url(
                "http://evil.example.com/",
                resolver=fake_resolver("10.1.2.3"),
            )

    def test_공인_IP로_해석되는_호스트명은_검증된_IP를_반환한다(self):
        def resolve_multiple(_hostname, _port, type):
            return [
                (2, type, 6, "", ("93.184.216.34", 0)),
                (2, type, 6, "", ("1.1.1.1", 0)),
            ]

        # 여러 주소가 해석돼도 실제로 연결에 쓰일 첫 번째 주소를 반환해야 한다.
        assert (
            validate_fetch_url(
                "https://good.example.com/",
                resolver=resolve_multiple,
            )
            == "93.184.216.34"
        )

    def test_리졸버를_전달하지_않으면_DNS_기반_검증을_건너뛴다(self):
        # resolver가 없으면 DNS 검증 경로 자체를 건너뛴다(호출자가 옵트인해야 함).
        assert validate_fetch_url("https://unresolved.example.com/") is None

    def test_호스트명이_루프백_주소로_해석되면_URL_검증이_거부한다(self):
        def resolve_loopback(_hostname, _port, type):
            return [(2, type, 6, "", ("127.0.0.1", 0))]

        with pytest.raises(UnsafeFetchUrlError):
            validate_fetch_url("https://public.example/event", resolver=resolve_loopback)

    def test_호스트명이_IPv4_매핑_루프백_주소로_해석되면_거부된다(self):
        def resolve_mapped_loopback(_hostname, _port, type):
            return [(10, type, 6, "", ("::ffff:127.0.0.1", 0, 0, 0))]

        with pytest.raises(UnsafeFetchUrlError):
            validate_fetch_url("https://public.example/event", resolver=resolve_mapped_loopback)
