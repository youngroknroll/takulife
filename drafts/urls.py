from django.urls import path

from .views import (
    AdminEventDraftApproveView,
    AdminEventDraftDetailView,
    AdminEventDraftListCreateView,
    AdminEventDraftRejectView,
)


urlpatterns = [
    path("event-drafts/", AdminEventDraftListCreateView.as_view(), name="admin-event-drafts"),
    path("event-drafts/<int:pk>/", AdminEventDraftDetailView.as_view(), name="admin-event-draft-detail"),
    path(
        "event-drafts/<int:pk>/approve/",
        AdminEventDraftApproveView.as_view(),
        name="admin-event-draft-approve",
    ),
    path(
        "event-drafts/<int:pk>/reject/",
        AdminEventDraftRejectView.as_view(),
        name="admin-event-draft-reject",
    ),
]
