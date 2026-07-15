"""core.ip: proxy-aware client IP resolution.

(.docs/plans/2026-07-14-stage0-deployment-foundation-plan.md §8 PR-0d,
TDD Coach checkpoints CP-7..CP-11)
"""

from django.test import RequestFactory, override_settings

from core.ip import get_client_ip, resolve_client_ip


def test_resolve_client_ip_ignores_forwarded_header_when_trusted_proxy_count_unset():
    ip = resolve_client_ip(
        remote_addr="10.0.0.5",
        forwarded_for="203.0.113.9",
        trusted_proxy_count=None,
    )

    assert ip == "10.0.0.5"


def test_resolve_client_ip_returns_rightmost_nth_hop_when_trusted_proxy_count_set():
    ip = resolve_client_ip(
        remote_addr="10.0.0.5",
        forwarded_for="203.0.113.9",
        trusted_proxy_count=1,
    )

    assert ip == "203.0.113.9"

    ip = resolve_client_ip(
        remote_addr="10.0.0.5",
        forwarded_for="198.51.100.1, 203.0.113.9",
        trusted_proxy_count=1,
    )

    assert ip == "203.0.113.9"


def test_resolve_client_ip_falls_back_to_remote_addr_when_forwarded_header_missing_or_too_short():
    assert (
        resolve_client_ip(
            remote_addr="10.0.0.5", forwarded_for="", trusted_proxy_count=1
        )
        == "10.0.0.5"
    )

    assert (
        resolve_client_ip(
            remote_addr="10.0.0.5",
            forwarded_for="203.0.113.9",
            trusted_proxy_count=2,
        )
        == "10.0.0.5"
    )


def test_get_client_ip_uses_remote_addr_when_trusted_proxy_count_unset():
    request = RequestFactory().get(
        "/",
        REMOTE_ADDR="10.0.0.5",
        HTTP_X_FORWARDED_FOR="203.0.113.9",
    )

    assert get_client_ip(request) == "10.0.0.5"


@override_settings(TRUSTED_PROXY_COUNT=1)
def test_get_client_ip_parses_forwarded_header_when_trusted_proxy_count_set():
    request = RequestFactory().get(
        "/",
        REMOTE_ADDR="10.0.0.5",
        HTTP_X_FORWARDED_FOR="203.0.113.9",
    )

    assert get_client_ip(request) == "203.0.113.9"
