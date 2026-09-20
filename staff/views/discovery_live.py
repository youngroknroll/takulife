"""대시보드가 폴링으로 갱신하는 수집 실시간 현황 API."""
from rest_framework.permissions import IsAdminUser
from rest_framework.views import APIView


class StaffDiscoveryLiveView(APIView):
    permission_classes = [IsAdminUser]
