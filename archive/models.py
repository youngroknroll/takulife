from django.conf import settings
from django.db import models

from events.models import Event

from .querysets import UserEventStatusQuerySet


class EventInterest(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="archive_event_interests",
    )
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="archive_user_interests")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "event"],
                name="unique_archive_user_event_interest",
            ),
        ]


class UserEventStatus(models.Model):
    class Status(models.TextChoices):
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
    # When True, the user opted this planned row out of auto-miss (revert from
    # an auto-derived 'missed' back to planned). Only consulted on the planned
    # branch of the derivation; visited/missed already short-circuit.
    missed_overridden = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserEventStatusQuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "event"],
                name="unique_archive_user_event_status",
            ),
        ]


class PersonalEntry(models.Model):
    """A user-owned, private, *unofficial* archive subject.

    Unlike Event (curated, admin-reviewed, public), a PersonalEntry is something
    the user found or owns themselves — an unofficial goods cafe, a product they
    bought, etc. It is always private to its owner and never appears in the public
    catalog. Archive actions (interest/status/visit) will be able to point at one
    of these instead of an Event in later phases.
    """

    class Kind(models.TextChoices):
        PLACE = "place", "Place"
        GOODS = "goods", "Goods"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="archive_personal_entries",
    )
    kind = models.CharField(max_length=20, choices=Kind.choices)
    title = models.CharField(max_length=255)
    category = models.CharField(max_length=100, blank=True)
    work_title = models.CharField(max_length=255, blank=True)
    location_name = models.CharField(max_length=255, blank=True)
    region = models.CharField(max_length=100, blank=True)
    # A user reference link (tweet / blog / shop). NOT unique and NOT "official".
    url = models.URLField(blank=True)
    memo = models.TextField(blank=True)
    image = models.ImageField(upload_to="personal-entries/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


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
