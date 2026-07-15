"""Proxy-aware client IP resolution.

Wired into django-axes via ``AXES_CLIENT_IP_CALLABLE`` (see
``config.settings.build_axes_client_ip_callable``) rather than axes' own
``AXES_IPWARE_*`` settings: those require the optional ``django-ipware``
dependency, which this project does not install, so they are dead
configuration that silently does nothing. ``AXES_CLIENT_IP_CALLABLE`` is
axes' first-priority IP source (see ``axes/helpers.py``) and needs no extra
dependency.

Trusts ``X-Forwarded-For`` only when ``TRUSTED_PROXY_COUNT`` is explicitly
configured, and only the rightmost N hops of that header — the left end of
the chain is attacker-controlled (any client can send an arbitrary
``X-Forwarded-For`` header), while the right end is appended by each proxy
hop the deployment actually trusts.
"""


def resolve_client_ip(*, remote_addr, forwarded_for, trusted_proxy_count):
    """Return the client IP given raw request values.

    When ``trusted_proxy_count`` is falsy (None or 0), ``forwarded_for`` is
    not even inspected — this is the spoofing-safe default matching
    historical REMOTE_ADDR-only behavior. When set, the Nth-from-the-right
    hop of ``forwarded_for`` is used, falling back to ``remote_addr`` when
    the header is missing or has fewer hops than ``trusted_proxy_count``.
    """
    if not trusted_proxy_count:
        return remote_addr

    hops = [hop.strip() for hop in forwarded_for.split(",") if hop.strip()]
    if len(hops) < trusted_proxy_count:
        return remote_addr

    return hops[-trusted_proxy_count]


def get_client_ip(request):
    """Resolve the client IP for a Django ``request`` using the deployment's
    ``TRUSTED_PROXY_COUNT`` setting (unset/0 disables X-Forwarded-For
    parsing entirely)."""
    from django.conf import settings

    return resolve_client_ip(
        remote_addr=request.META.get("REMOTE_ADDR"),
        forwarded_for=request.META.get("HTTP_X_FORWARDED_FOR", ""),
        trusted_proxy_count=getattr(settings, "TRUSTED_PROXY_COUNT", None),
    )
