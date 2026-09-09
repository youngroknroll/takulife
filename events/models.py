from datetime import timedelta

from django.db import models
from django.utils import timezone

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
    view_count = models.PositiveIntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    objects = EventQuerySet.as_manager()

    def __str__(self):
        return self.title

    def needs_reverification(self, *, today):
        """D-7 재확인 대상인지 쿼리 없이 판정한다(목록 행마다 재조회 금지).

        events/queries.py의 _needs_reverification_qs와 같은 규칙: 시작일·종료일이
        모두 있고 시작일-7일 <= today <= 종료일이며, 한 번도 검증되지 않았거나
        마지막 검증일이 그 D-7 기준일보다 이전이면 True.
        """
        if self.start_date is None or self.end_date is None:
            return False
        reverify_deadline = self.start_date - timedelta(days=7)
        if not (self.end_date >= today and reverify_deadline <= today):
            return False
        if self.verified_at is None:
            return True
        return timezone.localtime(self.verified_at).date() < reverify_deadline
