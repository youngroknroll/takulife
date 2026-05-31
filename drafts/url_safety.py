from ipaddress import ip_address
from urllib.parse import urlparse


class InvalidFetchUrlError(Exception):
    pass


class UnsafeFetchUrlError(Exception):
    pass


def _is_unsafe_ip(value):
    return (
        value.is_private
        or value.is_loopback
        or value.is_link_local
        or value.is_multicast
        or value.is_unspecified
        or value.is_reserved
    )


def validate_fetch_url(url):
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        raise InvalidFetchUrlError

    if not parsed.hostname:
        raise InvalidFetchUrlError

    hostname = parsed.hostname.strip().lower()
    if hostname == "localhost":
        raise UnsafeFetchUrlError

    try:
        parsed_ip = ip_address(hostname)
    except ValueError:
        return

    if _is_unsafe_ip(parsed_ip):
        raise UnsafeFetchUrlError
