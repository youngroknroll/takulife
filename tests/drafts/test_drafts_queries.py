"""drafts/queries.py 테스트: list_drafts()와 DRAFT_LISTING_PAGE_SIZE.
list_draft_sources()는 -enabled, name 순 정렬을 검증하며, staff 대시보드는
DraftSource를 직접 조회하지 않고 이 헬퍼를 거쳐야 한다."""
import pytest

from drafts.models import DraftSource, EventDraft

pytestmark = pytest.mark.domain


@pytest.mark.django_db
class TestDraftReviewStats:
    def test_드래프트가_없으면_세_상태_카운트가_모두_0으로_반환된다(self):
        from drafts.queries import draft_review_stats

        result = draft_review_stats()

        assert set(result.keys()) == {"pending", "approved", "rejected"}
        assert result["pending"] == 0
        assert result["approved"] == 0
        assert result["rejected"] == 0

    def test_드래프트_상태별_개수가_실제_분포와_일치한다(self, make_draft):
        from drafts.queries import draft_review_stats

        make_draft("https://example.com/a")
        make_draft("https://example.com/b")
        make_draft("https://example.com/c", review_status=EventDraft.ReviewStatus.APPROVED)
        make_draft("https://example.com/d", review_status=EventDraft.ReviewStatus.REJECTED)

        result = draft_review_stats()

        assert result["pending"] == 2
        assert result["approved"] == 1
        assert result["rejected"] == 1

    def test_pending_드래프트만_있어도_세_키가_모두_포함된다(self, make_draft):
        from drafts.queries import draft_review_stats

        make_draft("https://example.com/only-pending")

        result = draft_review_stats()

        assert result["pending"] == 1
        assert result["approved"] == 0
        assert result["rejected"] == 0

    def test_approved_드래프트만_있어도_세_키가_모두_포함된다(self, make_draft):
        from drafts.queries import draft_review_stats

        make_draft("https://example.com/only-approved", review_status=EventDraft.ReviewStatus.APPROVED)

        result = draft_review_stats()

        assert result["pending"] == 0
        assert result["approved"] == 1
        assert result["rejected"] == 0


@pytest.mark.django_db
class TestListDrafts:
    def test_상태_필터_없이_조회하면_전체_드래프트를_최신순으로_반환한다(self, make_draft):
        from drafts.queries import list_drafts

        first = make_draft("https://example.com/1")
        second = make_draft("https://example.com/2")
        third = make_draft("https://example.com/3")

        result = list(list_drafts())

        assert result == [third, second, first]

    def test_pending_필터는_승인_거절된_드래프트를_제외한다(self, make_draft):
        from drafts.queries import list_drafts

        pending = make_draft("https://example.com/pending")
        make_draft("https://example.com/approved", review_status=EventDraft.ReviewStatus.APPROVED)
        make_draft("https://example.com/rejected", review_status=EventDraft.ReviewStatus.REJECTED)

        result = list(list_drafts(status=EventDraft.ReviewStatus.PENDING))

        assert result == [pending]

    def test_필터링된_결과도_최신순_정렬을_유지한다(self, make_draft):
        from drafts.queries import list_drafts

        older = make_draft("https://example.com/older-pending")
        make_draft("https://example.com/approved-between", review_status=EventDraft.ReviewStatus.APPROVED)
        newer = make_draft("https://example.com/newer-pending")

        result = list(list_drafts(status=EventDraft.ReviewStatus.PENDING))

        assert result == [newer, older]

    def test_존재하지_않는_상태값으로_조회하면_빈_목록을_반환한다(self, make_draft):
        from drafts.queries import list_drafts

        make_draft("https://example.com/only-pending")

        result = list(list_drafts(status="garbage"))

        assert result == []

    def test_각_상태_필터의_개수가_레코드가_여러_건이어도_정확히_집계된다(self, make_draft):
        from drafts.queries import list_drafts

        for i in range(2):
            make_draft(f"https://example.com/pending-{i}")
        for i in range(3):
            make_draft(f"https://example.com/approved-{i}", review_status=EventDraft.ReviewStatus.APPROVED)
        for i in range(2):
            make_draft(f"https://example.com/rejected-{i}", review_status=EventDraft.ReviewStatus.REJECTED)

        assert list_drafts(status=EventDraft.ReviewStatus.PENDING).count() == 2
        assert list_drafts(status=EventDraft.ReviewStatus.APPROVED).count() == 3
        assert list_drafts(status=EventDraft.ReviewStatus.REJECTED).count() == 2


def test_드래프트_목록_페이지_크기_상수는_14이다():
    """스태프 콘솔 개편(D8)으로 밀도가 10→14로 바뀐 값을 그대로 반영한다."""
    from drafts.queries import DRAFT_LISTING_PAGE_SIZE

    assert DRAFT_LISTING_PAGE_SIZE == 14


@pytest.mark.django_db
class TestListDraftSources:
    def test_활성화된_소스가_비활성_소스보다_먼저_정렬된다(self):
        from drafts.queries import list_draft_sources

        disabled = DraftSource.objects.create(
            name="disabled-source",
            url="https://example.com/disabled-feed/",
            source_type=DraftSource.SourceType.RSS,
            enabled=False,
        )
        enabled = DraftSource.objects.create(
            name="enabled-source",
            url="https://example.com/enabled-feed/",
            source_type=DraftSource.SourceType.RSS,
            enabled=True,
        )

        result = list(list_draft_sources())

        assert result == [enabled, disabled]

    def test_같은_활성_상태_내에서는_이름순으로_정렬된다(self):
        from drafts.queries import list_draft_sources

        zeta = DraftSource.objects.create(
            name="zeta",
            url="https://example.com/zeta/",
            source_type=DraftSource.SourceType.SITEMAP,
            enabled=True,
        )
        alpha = DraftSource.objects.create(
            name="alpha",
            url="https://example.com/alpha/",
            source_type=DraftSource.SourceType.SITEMAP,
            enabled=True,
        )

        result = list(list_draft_sources())

        assert result == [alpha, zeta]

    def test_소스가_없으면_빈_목록을_반환한다(self):
        from drafts.queries import list_draft_sources

        result = list(list_draft_sources())

        assert result == []


@pytest.mark.django_db
class TestEnabledDraftSourcesExist:
    def test_소스가_없으면_활성_소스_존재_여부가_거짓이다(self):
        from drafts.queries import enabled_draft_sources_exist

        assert enabled_draft_sources_exist() is False

    def test_비활성_소스만_있으면_활성_소스_존재_여부가_거짓이다(self):
        from drafts.queries import enabled_draft_sources_exist

        DraftSource.objects.create(
            name="disabled-source",
            url="https://example.com/disabled-feed/",
            source_type=DraftSource.SourceType.RSS,
            enabled=False,
        )

        assert enabled_draft_sources_exist() is False

    def test_활성_소스가_하나라도_있으면_존재_여부가_참이다(self):
        from drafts.queries import enabled_draft_sources_exist

        DraftSource.objects.create(
            name="enabled-source",
            url="https://example.com/enabled-feed/",
            source_type=DraftSource.SourceType.RSS,
            enabled=True,
        )

        assert enabled_draft_sources_exist() is True


@pytest.mark.django_db
class TestDraftSearch:
    """커맨드바 검색이 넘기는 q를 처리한다. 검수자가 기억하는 단서는 제목이거나
    출처라, 둘 중 어느 쪽으로 쳐도 찾혀야 한다."""

    def _make(self, **kwargs):
        base = {
            "source_url": f"https://example.com/{kwargs.get('source_name', 'x')}",
            "source_name": "기본 소스",
            "raw_title": "원본 제목",
            "raw_text": "본문",
        }
        return EventDraft.objects.create(**{**base, **kwargs})

    def test_추출된_제목의_일부로_찾는다(self):
        from drafts.queries import list_drafts

        hit = self._make(source_url="https://a.test/1", extracted_title="여름 애니 팝업스토어")
        self._make(source_url="https://a.test/2", extracted_title="겨울 전시")

        assert list(list_drafts(search="팝업")) == [hit]

    def test_추출_제목이_비어_있으면_원본_제목으로도_찾는다(self):
        from drafts.queries import list_drafts

        hit = self._make(source_url="https://b.test/1", raw_title="한정 굿즈 예약")
        self._make(source_url="https://b.test/2", raw_title="다른 것")

        assert list(list_drafts(search="굿즈")) == [hit]

    def test_출처_이름으로도_찾는다(self):
        from drafts.queries import list_drafts

        hit = self._make(source_url="https://c.test/1", source_name="트위터 공식")
        self._make(source_url="https://c.test/2", source_name="블로그")

        assert list(list_drafts(search="트위터")) == [hit]

    def test_대소문자를_구분하지_않는다(self):
        from drafts.queries import list_drafts

        hit = self._make(source_url="https://d.test/1", extracted_title="Anime Popup")

        assert list(list_drafts(search="anime popup")) == [hit]

    def test_검색어와_상태_필터는_함께_적용된다(self):
        from drafts.queries import list_drafts

        hit = self._make(
            source_url="https://e.test/1",
            extracted_title="굿즈 예약",
            review_status=EventDraft.ReviewStatus.PENDING,
        )
        self._make(
            source_url="https://e.test/2",
            extracted_title="굿즈 예약",
            review_status=EventDraft.ReviewStatus.APPROVED,
        )

        assert list(list_drafts(status="pending", search="굿즈")) == [hit]

    def test_빈_검색어는_아무것도_거르지_않는다(self):
        from drafts.queries import list_drafts

        self._make(source_url="https://f.test/1")
        self._make(source_url="https://f.test/2")

        assert list_drafts(search="   ").count() == 2
