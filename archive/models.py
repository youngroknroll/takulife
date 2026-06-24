from django.conf import settings
from django.db import models

from events.models import Event


class UserEventStatus(models.Model):
    class Status(models.TextChoices):
        INTERESTED = "interested", "Interested"
        PLANNED = "planned", "Planned"
        VISITED = "visited", "Visited"
        MISSED = "missed", "Missed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="archive_event_statuses",
    )
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="archive_user_statuses")
    status = models.CharField(max_length=20, choices=Status.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "event"],
                name="unique_archive_user_event_status",
            ),
        ]


class VisitRecord(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="archive_visit_records",
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="archive_visit_records",
    )
    visited_on = models.DateField()
    short_review = models.CharField(max_length=255, blank=True)


class VisitRecordPhoto(models.Model):
    visit_record = models.ForeignKey(
        VisitRecord,
        on_delete=models.CASCADE,
        related_name="photos",
    )
    image = models.ImageField(upload_to="visit-record-photos/")
