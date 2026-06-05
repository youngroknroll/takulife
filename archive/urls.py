from django.urls import path

from .views import UserEventStatusDetailView, UserEventStatusListCreateView


urlpatterns = [
    path("", UserEventStatusListCreateView.as_view(), name="user-event-status-list-create"),
    path("<int:pk>/", UserEventStatusDetailView.as_view(), name="user-event-status-detail"),
]
