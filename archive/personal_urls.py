from django.urls import path

from . import views

urlpatterns = [
    path(
        "",
        views.PersonalEntryListCreateView.as_view(),
        name="personal-entry-list-create",
    ),
    path(
        "<int:pk>/",
        views.PersonalEntryDetailView.as_view(),
        name="personal-entry-detail",
    ),
]
