from django.urls import path

from .views import AdminEventDraftListCreateView


urlpatterns = [
    path("event-drafts/", AdminEventDraftListCreateView.as_view(), name="admin-event-drafts"),
]
