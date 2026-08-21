from ipaddress import ip_address
import socket
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


def validate_fetch_url(url, *, resolver=None):
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
        if resolver is None:
            return

        addresses = resolver(hostname, parsed.port or 443, type=socket.SOCK_STREAM)
        for address_info in addresses:
            resolved_ip = ip_address(address_info[4][0])
            if _is_unsafe_ip(resolved_ip):
                raise UnsafeFetchUrlError
        # 실제 연결에 쓰일 주소를 반환해 호출자가 DNS 재조회 없이 같은 IP로 접속하게 한다.
        return str(ip_address(addresses[0][4][0]))

    if _is_unsafe_ip(parsed_ip):
        raise UnsafeFetchUrlError
    return str(parsed_ip)
