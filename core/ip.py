"""프록시를 인식하는 클라이언트 IP 해석.

axes 자체 ``AXES_IPWARE_*`` 설정 대신 ``AXES_CLIENT_IP_CALLABLE``
(``config.settings.build_axes_client_ip_callable`` 참고)로
django-axes에 연결한다: 그 설정들은 이 프로젝트에 설치하지 않은 선택적
``django-ipware`` 의존성이 필요해서 조용히 아무 동작도 안 하는 죽은
설정이 된다. ``AXES_CLIENT_IP_CALLABLE``은 axes가 가장 먼저 확인하는 IP
소스라 추가 의존성이 필요 없다.

``TRUSTED_PROXY_COUNT``가 명시적으로 설정된 경우에만, 그리고 그 헤더의
오른쪽에서 N개 홉만 ``X-Forwarded-For``를 신뢰한다 — 체인의 왼쪽 끝은
공격자가 조작할 수 있고(어떤 클라이언트든 임의의 ``X-Forwarded-For``
헤더를 보낼 수 있다), 오른쪽 끝은 배포가 실제로 신뢰하는 각 프록시
홉이 덧붙인 값이다.
"""


def resolve_client_ip(*, remote_addr, forwarded_for, trusted_proxy_count):
    """원시 요청 값으로 클라이언트 IP를 반환한다.

    ``trusted_proxy_count``가 falsy(None 또는 0)면 ``forwarded_for``는
    아예 검사하지 않는다 — 기존 REMOTE_ADDR 전용 동작과 같은,
    스푸핑에 안전한 기본값이다. 설정돼 있으면 ``forwarded_for``의
    오른쪽에서 N번째 홉을 쓰고, 헤더가 없거나 홉 수가
    ``trusted_proxy_count``보다 적으면 ``remote_addr``로 대체한다.
    """
    if not trusted_proxy_count:
        return remote_addr

    hops = [hop.strip() for hop in forwarded_for.split(",") if hop.strip()]
    if len(hops) < trusted_proxy_count:
        return remote_addr

    return hops[-trusted_proxy_count]


def get_client_ip(request):
    """배포의 ``TRUSTED_PROXY_COUNT`` 설정을 이용해 Django ``request``의
    클라이언트 IP를 해석한다(미설정/0이면 X-Forwarded-For 파싱을 아예
    하지 않는다)."""
    from django.conf import settings

    return resolve_client_ip(
        remote_addr=request.META.get("REMOTE_ADDR"),
        forwarded_for=request.META.get("HTTP_X_FORWARDED_FOR", ""),
        trusted_proxy_count=getattr(settings, "TRUSTED_PROXY_COUNT", None),
    )
