from django.conf import settings
from django.db import models


class EventDraft(models.Model):
    class ReviewStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    class ExtractionMethod(models.TextChoices):
        HEURISTIC = "heuristic", "Heuristic"
        LLM = "llm", "LLM"

    source_url = models.URLField(unique=True)
    source_name = models.CharField(max_length=100, blank=True)
    raw_title = models.CharField(max_length=255, blank=True)
    raw_text = models.TextField(blank=True)
    extracted_title = models.CharField(max_length=255, blank=True)
    extracted_category = models.CharField(max_length=100, blank=True)
    extracted_work_title = models.CharField(max_length=255, blank=True)
    extracted_location_name = models.CharField(max_length=255, blank=True)
    extracted_region = models.CharField(max_length=100, blank=True)
    extracted_start_date = models.DateField(null=True, blank=True)
    extracted_end_date = models.DateField(null=True, blank=True)
    extracted_summary = models.TextField(blank=True)
    extraction_method = models.CharField(
        max_length=20,
        choices=ExtractionMethod.choices,
        default=ExtractionMethod.HEURISTIC,
    )
    confidence = models.FloatField(null=True, blank=True)
    review_status = models.CharField(
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, default="")

    def __str__(self):
        return self.source_url


class DraftSource(models.Model):
    class SourceType(models.TextChoices):
        RSS = "rss", "RSS"
        SITEMAP = "sitemap", "Sitemap"
        HTML = "html", "HTML"

    name = models.CharField(max_length=100)
    url = models.URLField(unique=True)
    source_type = models.CharField(max_length=20, choices=SourceType.choices)
    enabled = models.BooleanField(default=False)
    link_selector = models.CharField(max_length=255, blank=True)
    last_checked_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)

    def __str__(self):
        return self.name
