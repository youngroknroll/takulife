"""러너 토큰 인증·속도 제한 공용 베이스 — drafts와 events가 함께 쓴다."""

import hashlib

from django.conf import settings
from django.utils.crypto import constant_time_compare
from rest_framework.permissions import BasePermission
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView


class IsDiscoveryRunner(BasePermission):
    def has_permission(self, request, view):
        token = settings.DRAFT_DISCOVERY_RUNNER_TOKEN
        if not token:
            # constant_time_compare("", "") == True인 함정을 막기 위해
            # 빈 설정에서는 비교 전에 명시적으로 거부한다.
            return False
        return constant_time_compare(request.headers.get("X-Runner-Token", ""), token)


class RunnerTokenThrottle(ScopedRateThrottle):
    """이 API는 미인증 뷰라 DRF 기본 스로틀이 요청 IP를 식별자로 쓰는데,
    저장소에 프록시 개수 설정이 없어 X-Forwarded-For 헤더를 그대로 믿는다.
    헤더만 바꿔 보내면 분당 상한을 무한히 우회할 수 있어, IP 대신 러너
    토큰 하나로 정하는 단일 버킷으로 센다."""

    def get_cache_key(self, request, view):
        # 토큰 원문을 캐시 키에 그대로 넣지 않는다 — 비밀이 캐시에 평문으로
        # 남는 것을 막기 위해 해시로 바꾼다.
        token = settings.DRAFT_DISCOVERY_RUNNER_TOKEN
        ident = hashlib.sha256(token.encode()).hexdigest()

        return self.cache_format % {"scope": self.scope, "ident": ident}


class RunnerAPIView(APIView):
    authentication_classes = []
    permission_classes = [IsDiscoveryRunner]
    throttle_classes = [RunnerTokenThrottle]
    throttle_scope = "discovery_runner"
