"""대시보드가 폴링으로 갱신하는 수집 실시간 현황 API."""
from django.utils import timezone
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from drafts.queries import recent_discovery_runs, runner_live_summary
from drafts.serializers import DiscoveryRunnerLiveSerializer, DiscoveryRunSummarySerializer


class StaffDiscoveryLiveView(APIView):
    permission_classes = [IsAdminUser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "staff_discovery_live"

    def get(self, request):
        runner = DiscoveryRunnerLiveSerializer(runner_live_summary()).data
        runs = DiscoveryRunSummarySerializer(recent_discovery_runs(), many=True).data
        # 다른 시각 필드와 같은 +09:00 표기를 맞춘다.
        return Response({"runner": runner, "runs": runs, "server_time": timezone.localtime()})
