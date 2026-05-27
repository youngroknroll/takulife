from django.urls import path

from .views import PublicEventListView


urlpatterns = [
    path("", PublicEventListView.as_view(), name="event-list"),
]
