from django.urls import path

from .views import (
    AdminEventDraftApproveView,
    AdminEventDraftDetailView,
    AdminEventDraftListCreateView,
    AdminEventDraftRejectView,
    AdminEventDraftStatsView,
)


urlpatterns = [
    path("", AdminEventDraftListCreateView.as_view(), name="event-drafts"),
    path("stats/", AdminEventDraftStatsView.as_view(), name="event-draft-stats"),
    path("<int:pk>/", AdminEventDraftDetailView.as_view(), name="event-draft-detail"),
    path(
        "<int:pk>/approve/",
        AdminEventDraftApproveView.as_view(),
        name="event-draft-approve",
    ),
    path(
        "<int:pk>/reject/",
        AdminEventDraftRejectView.as_view(),
        name="event-draft-reject",
    ),
]
