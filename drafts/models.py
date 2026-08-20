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


class SourceDiscoveryRun(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CLAIMED = "claimed", "Claimed"
        SUCCEEDED = "succeeded", "Succeeded"
        PARTIALLY_FAILED = "partially_failed", "Partially failed"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"

    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    provider = models.CharField(max_length=50, blank=True)
    lease_token = models.CharField(max_length=64, blank=True)
    lease_expires_at = models.DateTimeField(null=True, blank=True)
    lease_count = models.PositiveSmallIntegerField(default=0)
    # 서버가 정의한 안전 문구만 담는다(후보·응답 원문 보간 금지).
    error_summary = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"run {self.pk} ({self.status})"


class SourceCandidate(models.Model):
    class Status(models.TextChoices):
        PROMOTED = "promoted", "Promoted"
        FAILED = "failed", "Failed"

    class FailureStage(models.TextChoices):
        SCHEMA = "schema", "Schema"
        DUPLICATE = "duplicate", "Duplicate"
        URL_SAFETY = "url_safety", "URL safety"
        ROBOTS = "robots", "Robots"
        FETCH = "fetch", "Fetch"
        LISTING_EXTRACTION = "listing_extraction", "Listing extraction"
        SAMPLE_CANARY = "sample_canary", "Sample canary"

    run = models.ForeignKey(
        SourceDiscoveryRun, on_delete=models.CASCADE, related_name="candidates"
    )
    name = models.CharField(max_length=100)
    url = models.URLField()
    source_type = models.CharField(
        max_length=20, choices=DraftSource.SourceType.choices
    )
    link_selector = models.CharField(max_length=255, blank=True)
    sample_url = models.URLField()
    official_basis = models.CharField(max_length=500, blank=True)
    note = models.CharField(max_length=500, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, blank=True)
    failure_stage = models.CharField(
        max_length=20, choices=FailureStage.choices, blank=True
    )
    # 단계별 서버 정의 메시지 + 예외 클래스명만(후보/응답 원문 보간 금지).
    failure_reason = models.CharField(max_length=255, blank=True)
    promoted_source = models.ForeignKey(
        DraftSource, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["run", "url"], name="uniq_source_candidate_run_url"
            )
        ]

    def __str__(self):
        return self.url


class DiscoveryRunnerStatus(models.Model):
    # 단일 행 계약: 서비스가 pk=1 update_or_create로 관리한다.
    last_heartbeat_at = models.DateTimeField()
    provider = models.CharField(max_length=50, blank=True)
