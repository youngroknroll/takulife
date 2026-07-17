"""core.ip: proxy-aware client IP resolution.

(.docs/plans/2026-07-14-stage0-deployment-foundation-plan.md §8 PR-0d,
TDD Coach checkpoints CP-7..CP-11)
"""

import pytest
from django.test import RequestFactory, override_settings

from core.ip import get_client_ip, resolve_client_ip

pytestmark = pytest.mark.unit


def test_trusted_proxy_count가_미설정이면_forwarded_헤더를_무시하고_remote_addr를_사용한다():
    ip = resolve_client_ip(
        remote_addr="10.0.0.5",
        forwarded_for="203.0.113.9",
        trusted_proxy_count=None,
    )

    assert ip == "10.0.0.5"


def test_trusted_proxy_count가_설정되면_forwarded_헤더에서_오른쪽에서_n번째_홉_주소를_반환한다():
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


def test_forwarded_헤더가_없거나_신뢰_홉_수보다_짧으면_remote_addr로_폴백한다():
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


def test_get_client_ip는_trusted_proxy_count가_미설정이면_remote_addr를_사용한다():
    request = RequestFactory().get(
        "/",
        REMOTE_ADDR="10.0.0.5",
        HTTP_X_FORWARDED_FOR="203.0.113.9",
    )

    assert get_client_ip(request) == "10.0.0.5"


@override_settings(TRUSTED_PROXY_COUNT=1)
def test_get_client_ip는_trusted_proxy_count가_설정되면_forwarded_헤더를_파싱해_반환한다():
    request = RequestFactory().get(
        "/",
        REMOTE_ADDR="10.0.0.5",
        HTTP_X_FORWARDED_FOR="203.0.113.9",
    )

    assert get_client_ip(request) == "203.0.113.9"
