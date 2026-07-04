"""Tests for drafts.models.DraftSource — the discovery-source registry model
(PR-2 of the auto-discovery plan, prompt_plan.md §2-1). Kept in a dedicated
file, mirroring tests/test_draft_models.py's per-field class layout.
"""
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from drafts.models import DraftSource


@pytest.mark.django_db
class TestDraftSourceCreation:
    def test_creates_with_required_fields(self):
        source = DraftSource.objects.create(
            name="atzip",
            url="https://atzip.kr/feed/",
            source_type=DraftSource.SourceType.RSS,
        )
        source.refresh_from_db()

        assert source.name == "atzip"
        assert source.url == "https://atzip.kr/feed/"
        assert source.source_type == DraftSource.SourceType.RSS

    def test_url_is_unique(self):
        """Two DraftSource rows pointing at the same feed/sitemap/board URL
        would make discover_drafts (PR-3) check and fetch it twice every
        run — the registry itself must reject the duplicate."""
        DraftSource.objects.create(
            name="atzip",
            url="https://atzip.kr/feed/",
            source_type=DraftSource.SourceType.RSS,
        )

        with pytest.raises(IntegrityError):
            with transaction.atomic():
                DraftSource.objects.create(
                    name="atzip duplicate",
                    url="https://atzip.kr/feed/",
                    source_type=DraftSource.SourceType.RSS,
                )


@pytest.mark.django_db
class TestSourceTypeField:
    @pytest.mark.parametrize(
        "source_type",
        [DraftSource.SourceType.RSS, DraftSource.SourceType.SITEMAP, DraftSource.SourceType.HTML],
    )
    def test_round_trips(self, source_type):
        source = DraftSource.objects.create(
            name="source", url="https://example.com/", source_type=source_type
        )
        source.refresh_from_db()

        assert source.source_type == source_type

    def test_invalid_choice_raises_validation_error_on_full_clean(self):
        source = DraftSource(
            name="source", url="https://example.com/", source_type="atom"
        )

        with pytest.raises(ValidationError):
            source.full_clean()


@pytest.mark.django_db
class TestEnabledField:
    def test_defaults_to_false(self):
        source = DraftSource.objects.create(
            name="source", url="https://example.com/", source_type=DraftSource.SourceType.RSS
        )

        assert source.enabled is False

    def test_true_value_round_trips(self):
        source = DraftSource.objects.create(
            name="source",
            url="https://example.com/",
            source_type=DraftSource.SourceType.RSS,
            enabled=True,
        )
        source.refresh_from_db()

        assert source.enabled is True


@pytest.mark.django_db
class TestLinkSelectorField:
    def test_defaults_to_blank_string(self):
        source = DraftSource.objects.create(
            name="source", url="https://example.com/", source_type=DraftSource.SourceType.HTML
        )

        assert source.link_selector == ""

    def test_selector_value_round_trips(self):
        source = DraftSource.objects.create(
            name="source",
            url="https://example.com/",
            source_type=DraftSource.SourceType.HTML,
            link_selector=".board-list a",
        )
        source.refresh_from_db()

        assert source.link_selector == ".board-list a"


@pytest.mark.django_db
class TestLastCheckedAtField:
    def test_defaults_to_none(self):
        source = DraftSource.objects.create(
            name="source", url="https://example.com/", source_type=DraftSource.SourceType.RSS
        )

        assert source.last_checked_at is None

    def test_datetime_value_round_trips(self):
        now = timezone.now()
        source = DraftSource.objects.create(
            name="source",
            url="https://example.com/",
            source_type=DraftSource.SourceType.RSS,
            last_checked_at=now,
        )
        source.refresh_from_db()

        assert source.last_checked_at.replace(microsecond=0) == now.replace(microsecond=0)


@pytest.mark.django_db
class TestLastErrorField:
    def test_defaults_to_blank_string(self):
        source = DraftSource.objects.create(
            name="source", url="https://example.com/", source_type=DraftSource.SourceType.RSS
        )

        assert source.last_error == ""

    def test_stores_long_error_message_without_truncation_or_db_error(self):
        """A CharField would either truncate silently or raise a Postgres
        DataError for a long exception string — this must go through
        .objects.create() directly (not full_clean(), which would just
        validate max_length rather than exercise the actual DB write path)
        so a CharField regression here is actually caught."""
        long_error = "x" * 5000

        source = DraftSource.objects.create(
            name="source",
            url="https://example.com/",
            source_type=DraftSource.SourceType.RSS,
            last_error=long_error,
        )
        source.refresh_from_db()

        assert source.last_error == long_error
