from django.urls import path

from .views import EventInterestDetailView, EventInterestListCreateView


urlpatterns = [
    path("", EventInterestListCreateView.as_view(), name="event-interest-list-create"),
    path("<int:pk>/", EventInterestDetailView.as_view(), name="event-interest-detail"),
]
