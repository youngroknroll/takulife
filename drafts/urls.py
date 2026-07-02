from django.urls import path

from .views import (
    AdminEventDraftDetailView,
    AdminEventDraftListCreateView,
    AdminEventDraftStatsView,
)


urlpatterns = [
    path("", AdminEventDraftListCreateView.as_view(), name="event-drafts"),
    path("stats/", AdminEventDraftStatsView.as_view(), name="event-draft-stats"),
    path("<int:pk>/", AdminEventDraftDetailView.as_view(), name="event-draft-detail"),
]
