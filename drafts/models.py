from django.db import models


class EventDraft(models.Model):
    class ReviewStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

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
    review_status = models.CharField(
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.source_url
