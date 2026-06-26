from django.db import models

from .querysets import EventQuerySet


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
    poster_image = models.ImageField(upload_to="event-posters/", blank=True, null=True)
    view_count = models.PositiveIntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    objects = EventQuerySet.as_manager()

    def __str__(self):
        return self.title
