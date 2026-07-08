"""Unit tests for drafts.url_safety — SSRF guard on draft-fetch URLs.

Covers the scheme/hostname rejections, literal-IP private-range blocking, and
the DNS-resolver path (a public hostname that resolves to a private address).
"""
import pytest

from drafts.url_safety import (
    InvalidFetchUrlError,
    UnsafeFetchUrlError,
    validate_fetch_url,
)


class TestSchemeAndHost:
    @pytest.mark.parametrize("url", ["ftp://example.com", "file:///etc/passwd", "javascript:alert(1)"])
    def test_non_http_scheme_rejected(self, url):
        with pytest.raises(InvalidFetchUrlError):
            validate_fetch_url(url)

    def test_missing_hostname_rejected(self):
        with pytest.raises(InvalidFetchUrlError):
            validate_fetch_url("http:///path-only")

    def test_localhost_rejected(self):
        with pytest.raises(UnsafeFetchUrlError):
            validate_fetch_url("http://localhost/page")


class TestLiteralIp:
    @pytest.mark.parametrize(
        "url",
        [
            "http://127.0.0.1/",
            "http://10.0.0.5/",
            "http://192.168.1.1/",
            "http://169.254.169.254/latest/meta-data/",  # cloud metadata
            "http://[::1]/",
            "http://0.0.0.0/",
        ],
    )
    def test_private_or_special_ip_rejected(self, url):
        with pytest.raises(UnsafeFetchUrlError):
            validate_fetch_url(url)

    def test_public_ip_allowed(self):
        # Returns None (no raise) for a public literal IP.
        assert validate_fetch_url("http://8.8.8.8/") is None


class TestResolverPath:
    def test_hostname_resolving_to_private_ip_rejected(self, fake_resolver):
        with pytest.raises(UnsafeFetchUrlError):
            validate_fetch_url(
                "http://evil.example.com/",
                resolver=fake_resolver("10.1.2.3"),
            )

    def test_hostname_resolving_to_public_ip_allowed(self, fake_resolver):
        assert (
            validate_fetch_url(
                "https://good.example.com/",
                resolver=fake_resolver("93.184.216.34"),
            )
            is None
        )

    def test_hostname_without_resolver_is_not_validated(self):
        # With no resolver the DNS path is skipped (caller opts in to resolution).
        assert validate_fetch_url("https://unresolved.example.com/") is None
