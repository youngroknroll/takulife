from django.urls import path

from staff.permissions import staff_api_korean
from staff.views import (
    AdminEventDraftDetailView,
    AdminEventDraftListCreateView,
    AdminEventDraftStatsView,
)

urlpatterns = [
    path("", staff_api_korean(AdminEventDraftListCreateView.as_view()), name="event-drafts"),
    path(
        "stats/",
        staff_api_korean(AdminEventDraftStatsView.as_view()),
        name="event-draft-stats",
    ),
    path(
        "<int:pk>/",
        staff_api_korean(AdminEventDraftDetailView.as_view()),
        name="event-draft-detail",
    ),
]
