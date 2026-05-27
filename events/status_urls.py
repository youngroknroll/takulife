from django.urls import path

from .views import UserEventStatusUpsertView, VisitRecordListCreateView, VisitRecordPhotoDeleteView, VisitRecordPhotoListCreateView


urlpatterns = [
    path("event-statuses/<int:event_id>/", UserEventStatusUpsertView.as_view(), name="event-status-upsert"),
    path("visit-records/", VisitRecordListCreateView.as_view(), name="visit-record-list-create"),
    path("visit-records/<int:record_id>/photos/", VisitRecordPhotoListCreateView.as_view(), name="visit-record-photo-create"),
    path("visit-records/<int:record_id>/photos/<int:photo_id>/", VisitRecordPhotoDeleteView.as_view(), name="visit-record-photo-delete"),
]
