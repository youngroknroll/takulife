from django.urls import path

from .views import (
    VisitRecordDetailView,
    VisitRecordListCreateView,
    VisitRecordPhotoCreateView,
    VisitRecordPhotoDeleteView,
)

urlpatterns = [
    path("", VisitRecordListCreateView.as_view(), name="visit-record-list-create"),
    path("<int:pk>/", VisitRecordDetailView.as_view(), name="visit-record-detail"),
    path("<int:record_id>/photos/", VisitRecordPhotoCreateView.as_view(), name="visit-record-photo-create"),
    path(
        "<int:record_id>/photos/<int:photo_id>/",
        VisitRecordPhotoDeleteView.as_view(),
        name="visit-record-photo-delete",
    ),
]
