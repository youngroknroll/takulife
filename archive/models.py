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
    # subject = exactly one of event (official) or personal_entry (unofficial).
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="archive_user_interests",
        null=True,
        blank=True,
    )
    personal_entry = models.ForeignKey(
        "PersonalEntry",
        on_delete=models.CASCADE,
        related_name="archive_user_interests",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="eventinterest_exactly_one_subject",
                condition=(
                    models.Q(event__isnull=False, personal_entry__isnull=True)
                    | models.Q(event__isnull=True, personal_entry__isnull=False)
                ),
            ),
            models.UniqueConstraint(
                fields=["user", "event"],
                condition=models.Q(event__isnull=False),
                name="unique_archive_user_event_interest",
            ),
            models.UniqueConstraint(
                fields=["user", "personal_entry"],
                condition=models.Q(personal_entry__isnull=False),
                name="unique_archive_user_personal_interest",
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
    # subject = exactly one of event (official) or personal_entry (unofficial).
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="archive_user_statuses",
        null=True,
        blank=True,
    )
    personal_entry = models.ForeignKey(
        "PersonalEntry",
        on_delete=models.CASCADE,
        related_name="archive_user_statuses",
        null=True,
        blank=True,
    )
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
            models.CheckConstraint(
                name="usereventstatus_exactly_one_subject",
                condition=(
                    models.Q(event__isnull=False, personal_entry__isnull=True)
                    | models.Q(event__isnull=True, personal_entry__isnull=False)
                ),
            ),
            models.UniqueConstraint(
                fields=["user", "event"],
                condition=models.Q(event__isnull=False),
                name="unique_archive_user_event_status",
            ),
            models.UniqueConstraint(
                fields=["user", "personal_entry"],
                condition=models.Q(personal_entry__isnull=False),
                name="unique_archive_user_personal_status",
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

    class PromotionStatus(models.TextChoices):
        # "" = never submitted for official review; "submitted" = a review draft
        # has been created. Set by the neutral core.promotion orchestrator (no FK
        # to drafts — archive must not depend on drafts).
        NONE = "", "None"
        SUBMITTED = "submitted", "Submitted"

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
    promotion_status = models.CharField(
        max_length=20,
        choices=PromotionStatus.choices,
        default=PromotionStatus.NONE,
        blank=True,
    )
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
    # subject = exactly one of event (official) or personal_entry (unofficial).
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="archive_visit_records",
        null=True,
        blank=True,
    )
    personal_entry = models.ForeignKey(
        PersonalEntry,
        on_delete=models.CASCADE,
        related_name="visit_records",
        null=True,
        blank=True,
    )
    visited_on = models.DateField()
    short_review = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                name="visitrecord_exactly_one_subject",
                condition=(
                    models.Q(event__isnull=False, personal_entry__isnull=True)
                    | models.Q(event__isnull=True, personal_entry__isnull=False)
                ),
            ),
        ]


class VisitRecordPhoto(models.Model):
    visit_record = models.ForeignKey(
        VisitRecord,
        on_delete=models.CASCADE,
        related_name="photos",
    )
    image = models.ImageField(upload_to="visit-record-photos/")
