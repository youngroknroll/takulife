from django.db import models


class Event(models.Model):
    class PublishStatus(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    title = models.CharField(max_length=255)
    category = models.CharField(max_length=100, blank=True)
    work_title = models.CharField(max_length=255, blank=True)
    location_name = models.CharField(max_length=255, blank=True)
    region = models.CharField(max_length=100, blank=True)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    official_url = models.URLField(unique=True, null=True, blank=True)
    source_name = models.CharField(max_length=100, blank=True)
    summary = models.TextField(blank=True)
    publish_status = models.CharField(
        max_length=20,
        choices=PublishStatus.choices,
        default=PublishStatus.DRAFT,
        db_index=True,
    )

    def __str__(self):
        return self.title


class UserEventStatus(models.Model):
    class Status(models.TextChoices):
        INTERESTED = "interested", "Interested"
        ATTENDED = "attended", "Attended"

    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="event_statuses")
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="user_statuses")
    status = models.CharField(max_length=20, choices=Status.choices)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "event"], name="unique_user_event_status"),
        ]


class VisitRecord(models.Model):
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="visit_records")
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="visit_records")
    visited_on = models.DateField()
    short_review = models.CharField(max_length=255, blank=True)


class VisitRecordPhoto(models.Model):
    visit_record = models.ForeignKey(VisitRecord, on_delete=models.CASCADE, related_name="photos")
    image = models.FileField(upload_to="visit-record-photos/")
