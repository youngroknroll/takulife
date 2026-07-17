"""Tests for drafts.models.DraftSource — the discovery-source registry model
(PR-2 of the auto-discovery plan, prompt_plan.md §2-1). Kept in a dedicated
file, mirroring tests/test_draft_models.py's per-field class layout.
"""
import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from drafts.models import DraftSource

pytestmark = pytest.mark.domain


@pytest.mark.django_db
class TestDraftSourceCreation:
    def test_필수_필드만_지정하면_드래프트_소스가_생성된다(self):
        source = DraftSource.objects.create(
            name="atzip",
            url="https://atzip.kr/feed/",
            source_type=DraftSource.SourceType.RSS,
        )
        source.refresh_from_db()

        assert source.name == "atzip"
        assert source.url == "https://atzip.kr/feed/"
        assert source.source_type == DraftSource.SourceType.RSS

    def test_동일한_url로_드래프트_소스를_중복_생성하면_무결성_오류가_난다(self):
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
        ids=["RSS", "사이트맵", "HTML"],
    )
    def test_source_type_값을_저장하면_그대로_유지된다(self, source_type):
        source = DraftSource.objects.create(
            name="source", url="https://example.com/", source_type=source_type
        )
        source.refresh_from_db()

        assert source.source_type == source_type

    def test_source_type에_허용되지_않은_값을_지정하면_full_clean에서_검증_오류가_난다(self):
        source = DraftSource(
            name="source", url="https://example.com/", source_type="atom"
        )

        with pytest.raises(ValidationError):
            source.full_clean()


@pytest.mark.django_db
class TestEnabledField:
    def test_enabled를_지정하지_않으면_기본값_False로_저장된다(self):
        source = DraftSource.objects.create(
            name="source", url="https://example.com/", source_type=DraftSource.SourceType.RSS
        )

        assert source.enabled is False

    def test_enabled를_True로_저장하면_그대로_유지된다(self):
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
    def test_link_selector를_지정하지_않으면_기본값_빈_문자열로_저장된다(self):
        source = DraftSource.objects.create(
            name="source", url="https://example.com/", source_type=DraftSource.SourceType.HTML
        )

        assert source.link_selector == ""

    def test_link_selector에_css_선택자_값을_저장하면_그대로_유지된다(self):
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
    def test_last_checked_at를_지정하지_않으면_기본값_None으로_저장된다(self):
        source = DraftSource.objects.create(
            name="source", url="https://example.com/", source_type=DraftSource.SourceType.RSS
        )

        assert source.last_checked_at is None

    def test_last_checked_at에_일시_값을_저장하면_그대로_유지된다(self):
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
    def test_last_error를_지정하지_않으면_기본값_빈_문자열로_저장된다(self):
        source = DraftSource.objects.create(
            name="source", url="https://example.com/", source_type=DraftSource.SourceType.RSS
        )

        assert source.last_error == ""

    def test_last_error는_긴_오류_메시지도_잘림_없이_저장한다(self):
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
