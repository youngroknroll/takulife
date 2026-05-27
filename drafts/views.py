from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAdminUser

from .models import EventDraft
from .serializers import EventDraftSerializer


class AdminEventDraftListCreateView(ListCreateAPIView):
    permission_classes = [IsAdminUser]
    serializer_class = EventDraftSerializer
    queryset = EventDraft.objects.order_by("-id")
