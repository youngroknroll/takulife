"""로컬 에이전트 러너용 API — 얇은 어댑터. 인증·직렬화·상태코드만 다루고
상태 산출·검증은 drafts.discovery_runs·drafts.candidate_validation에 위임한다.
"""
import hashlib

from django.conf import settings
from django.utils.crypto import constant_time_compare
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from core.errors import error_response
from drafts.agent_drafts import (
    AgentDraftSchemaError,
    EventLimitExceededError,
    submit_agent_draft,
)
from drafts.candidate_validation import (
    MAX_CANDIDATES_PER_RUN,
    CandidateLimitExceededError,
    LeaseInvalidError,
    sanitize_text,
    submit_candidate,
)
from drafts.discovery import SNS_HOSTNAMES
from drafts.discovery_runs import claim, complete_run, record_heartbeat
from drafts.models import DraftSource, EventDraft, SourceDiscoveryRun
from drafts.url_safety import InvalidFetchUrlError, UnsafeFetchUrlError


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


class _RunnerAPIView(APIView):
    authentication_classes = []
    permission_classes = [IsDiscoveryRunner]
    throttle_classes = [RunnerTokenThrottle]
    throttle_scope = "discovery_runner"


def _clean_provider(data):
    provider = data.get("provider")
    if not isinstance(provider, str):
        provider = ""
    return sanitize_text(value=provider)[:50]


class RunnerHeartbeatView(_RunnerAPIView):
    # 비밀 토큰 기반 기계 간 러너 경계라 공개 API 문서에서 제외한다.
    @extend_schema(exclude=True)
    def post(self, request):
        record_heartbeat(provider=_clean_provider(request.data))
        return Response(status=status.HTTP_204_NO_CONTENT)


class RunnerClaimView(_RunnerAPIView):
    # 비밀 토큰 기반 기계 간 러너 경계라 공개 API 문서에서 제외한다.
    @extend_schema(exclude=True)
    def post(self, request):
        run = claim(provider=_clean_provider(request.data))
        if run is None:
            return Response({"run": None})

        return Response(
            {
                "run": {
                    "run_id": run.pk,
                    "lease_token": run.lease_token,
                    "lease_expires_at": run.lease_expires_at.isoformat(),
                    "query": run.query,
                    "max_candidates": MAX_CANDIDATES_PER_RUN,
                    "existing_source_urls": list(
                        DraftSource.objects.values_list("url", flat=True)
                    ),
                    "excluded_hostnames": sorted(SNS_HOSTNAMES),
                }
            }
        )


class RunnerCandidateSubmitView(_RunnerAPIView):
    # 비밀 토큰 기반 기계 간 러너 경계라 공개 API 문서에서 제외한다.
    @extend_schema(exclude=True)
    def post(self, request, run_id):
        data = request.data
        lease_token = data.get("lease_token")
        candidate = data.get("candidate")
        if not isinstance(lease_token, str) or not isinstance(candidate, dict):
            return error_response("invalid candidate submission payload", status.HTTP_400_BAD_REQUEST)

        try:
            saved = submit_candidate(run_id=run_id, lease_token=lease_token, payload=candidate)
        except LeaseInvalidError:
            return error_response("lease is invalid or expired", status.HTTP_409_CONFLICT)
        except CandidateLimitExceededError:
            return error_response("candidate limit exceeded for this run", status.HTTP_400_BAD_REQUEST)

        return Response(
            {
                "url": saved.url,
                "status": saved.status,
                "failure_stage": saved.failure_stage,
                "failure_reason": saved.failure_reason,
            },
            status=status.HTTP_201_CREATED,
        )


class RunnerCompleteView(_RunnerAPIView):
    # 비밀 토큰 기반 기계 간 러너 경계라 공개 API 문서에서 제외한다.
    @extend_schema(exclude=True)
    def post(self, request, run_id):
        data = request.data
        lease_token = data.get("lease_token")
        runner_status = data.get("runner_status")
        failure_kind = data.get("failure_kind", "")
        if not isinstance(lease_token, str) or runner_status not in ("succeeded", "failed"):
            return error_response("invalid complete payload", status.HTTP_400_BAD_REQUEST)
        if not isinstance(failure_kind, str):
            failure_kind = ""

        try:
            run = complete_run(
                run_id=run_id,
                lease_token=lease_token,
                runner_status=runner_status,
                failure_kind=failure_kind,
            )
        except SourceDiscoveryRun.DoesNotExist:
            return error_response("run not found", status.HTTP_404_NOT_FOUND)
        except LeaseInvalidError:
            return error_response("lease is invalid or expired", status.HTTP_409_CONFLICT)

        return Response({"status": run.status})


class RunnerEventDraftSubmitView(_RunnerAPIView):
    # 비밀 토큰 기반 기계 간 러너 경계라 공개 API 문서에서 제외한다.
    @extend_schema(exclude=True)
    def post(self, request, run_id):
        data = request.data
        lease_token = data.get("lease_token")
        event = data.get("event")
        if not isinstance(lease_token, str) or not isinstance(event, dict):
            return error_response("invalid event submission payload", status.HTTP_400_BAD_REQUEST)

        try:
            draft, created = submit_agent_draft(run_id=run_id, lease_token=lease_token, payload=event)
        except LeaseInvalidError:
            return error_response("lease is invalid or expired", status.HTTP_409_CONFLICT)
        except EventLimitExceededError:
            return error_response("event limit exceeded for this run", status.HTTP_400_BAD_REQUEST)
        except AgentDraftSchemaError:
            return error_response("invalid event submission payload", status.HTTP_400_BAD_REQUEST)
        except (InvalidFetchUrlError, UnsafeFetchUrlError):
            return error_response("unsafe URL is not allowed", status.HTTP_400_BAD_REQUEST)

        if created:
            return Response(
                {"status": "created", "draft_id": draft.pk}, status=status.HTTP_201_CREATED
            )
        return Response({"status": "duplicate", "draft_id": draft.pk})


class RunnerKnownDraftUrlsView(_RunnerAPIView):
    # 비밀 토큰 기반 기계 간 러너 경계라 공개 API 문서에서 제외한다.
    @extend_schema(exclude=True)
    def post(self, request):
        urls = request.data.get("urls")
        if not isinstance(urls, list):
            return error_response("invalid known urls payload", status.HTTP_400_BAD_REQUEST)

        known_urls = set(
            EventDraft.objects.filter(source_url__in=urls).values_list(
                "source_url", flat=True
            )
        )
        unknown = [url for url in urls if url not in known_urls]

        return Response({"unknown": unknown})
