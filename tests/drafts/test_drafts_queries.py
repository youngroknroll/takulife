"""drafts/queries.py 테스트: list_drafts()와 DRAFT_LISTING_PAGE_SIZE.
list_draft_sources()는 -enabled, name 순 정렬을 검증하며, staff 대시보드는
DraftSource를 직접 조회하지 않고 이 헬퍼를 거쳐야 한다."""
from datetime import timedelta

import pytest
from django.utils import timezone

from drafts.discovery_runs import EVENT_OUTCOME_REASONS
from drafts.models import DraftSource, EventDraft, SourceCandidate, SourceDiscoveryRun

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
class TestDraftReviewSla:
    def test_드래프트가_전혀_없으면_최장_대기와_평균_처리와_반려율이_모두_None이고_카운트는_0이다(self):
        from drafts.queries import draft_review_sla

        now = timezone.now()

        result = draft_review_sla(now=now)

        assert result["longest_wait"] is None
        assert result["avg_handling"] is None
        assert result["rejection_rate"] is None
        assert result["pending_count"] == 0
        assert result["decided_count"] == 0
        assert result["rejected_count"] == 0

    def test_검토_대기_중인_드래프트가_여러_건이면_최장_대기는_가장_오래된_생성_시각_기준이다(self, make_draft):
        from drafts.queries import draft_review_sla

        now = timezone.now()
        # Given: 대기 드래프트 2건, 생성 시각이 다르다
        newer = make_draft()
        EventDraft.objects.filter(pk=newer.pk).update(created_at=now - timedelta(days=2))
        older = make_draft()
        EventDraft.objects.filter(pk=older.pk).update(created_at=now - timedelta(days=5))

        # When: SLA를 조회하면
        result = draft_review_sla(now=now)

        # Then: 최장 대기는 더 오래된 생성 시각 기준이다
        assert result["longest_wait"] == timedelta(days=5)
        assert result["pending_count"] == 2

    def test_재오픈된_대기_드래프트의_최장_대기는_재오픈_시각_기준이다(self, make_draft):
        from drafts.queries import draft_review_sla

        now = timezone.now()
        # Given: 아주 오래전 생성됐지만 최근 재오픈된 대기 드래프트
        draft = make_draft(reopened_at=now - timedelta(days=1))
        EventDraft.objects.filter(pk=draft.pk).update(created_at=now - timedelta(days=30))

        # When: SLA를 조회하면
        result = draft_review_sla(now=now)

        # Then: 최장 대기는 재오픈 시각 기준이다
        assert result["longest_wait"] == timedelta(days=1)

    def test_평균_처리와_반려율은_창_안에서_결정된_드래프트만_반영하고_창_밖_결정은_제외한다(self, make_draft):
        from drafts.queries import draft_review_sla

        now = timezone.now()
        # Given: 창 안에서 결정된 승인 1건과 창 밖에서 결정된 승인 1건
        in_window = make_draft(
            review_status=EventDraft.ReviewStatus.APPROVED,
            approved_at=now - timedelta(days=1),
        )
        EventDraft.objects.filter(pk=in_window.pk).update(created_at=now - timedelta(days=3))
        out_of_window = make_draft(
            review_status=EventDraft.ReviewStatus.APPROVED,
            approved_at=now - timedelta(days=10),
        )
        EventDraft.objects.filter(pk=out_of_window.pk).update(created_at=now - timedelta(days=20))

        # When: SLA를 조회하면
        result = draft_review_sla(now=now)

        # Then: 창 밖 결정은 제외되고 창 안 1건만 반영된다
        assert result["decided_count"] == 1
        assert result["avg_handling"] == timedelta(days=2)
        assert result["rejection_rate"] == 0.0

    def test_반려율은_창_안_결정_중_반려_비율로_계산된다(self, make_draft):
        from drafts.queries import draft_review_sla

        now = timezone.now()
        # Given: 창 안 반려 1건과 승인 3건
        rejected = make_draft(
            review_status=EventDraft.ReviewStatus.REJECTED,
            rejected_at=now - timedelta(days=1),
        )
        EventDraft.objects.filter(pk=rejected.pk).update(created_at=now - timedelta(days=2))
        for _ in range(3):
            approved = make_draft(
                review_status=EventDraft.ReviewStatus.APPROVED,
                approved_at=now - timedelta(days=1),
            )
            EventDraft.objects.filter(pk=approved.pk).update(created_at=now - timedelta(days=2))

        # When: SLA를 조회하면
        result = draft_review_sla(now=now)

        # Then: 반려율은 반려 1건 / 결정 4건이다
        assert result["rejection_rate"] == 0.25
        assert result["rejected_count"] == 1
        assert result["decided_count"] == 4

    def test_반려_후_재오픈되어_승인된_드래프트는_승인으로만_집계된다(self, make_draft):
        from drafts.queries import draft_review_sla

        now = timezone.now()
        # Given: 과거에 반려됐다가 재오픈되어 승인된 드래프트
        draft = make_draft(
            review_status=EventDraft.ReviewStatus.APPROVED,
            rejected_at=now - timedelta(days=4),
            rejection_reason="과거 반려",
            reopened_at=now - timedelta(days=3),
            approved_at=now - timedelta(days=1),
        )
        EventDraft.objects.filter(pk=draft.pk).update(created_at=now - timedelta(days=6))

        # When: SLA를 조회하면
        result = draft_review_sla(now=now)

        # Then: 승인으로만 집계되고 반려는 0건이다
        assert result["rejected_count"] == 0
        assert result["decided_count"] == 1
        assert result["rejection_rate"] == 0.0

    def test_재오픈_후_결정된_드래프트의_처리_시간은_재오픈_시각부터_계산한다(self, make_draft):
        from drafts.queries import draft_review_sla

        now = timezone.now()
        # Given: 재오픈 후 승인된 드래프트(재오픈 시각과 승인 시각의 차이는 2일)
        draft = make_draft(
            review_status=EventDraft.ReviewStatus.APPROVED,
            rejected_at=now - timedelta(days=4),
            rejection_reason="과거 반려",
            reopened_at=now - timedelta(days=3),
            approved_at=now - timedelta(days=1),
        )
        EventDraft.objects.filter(pk=draft.pk).update(created_at=now - timedelta(days=6))

        # When: SLA를 조회하면
        result = draft_review_sla(now=now)

        # Then: 처리 시간은 생성 시각이 아니라 재오픈 시각부터 계산된다
        assert result["avg_handling"] == timedelta(days=2)

    def test_결정_시각이_없는_레거시_승인_반려_건은_창_집계에서_제외된다(self, make_draft):
        from drafts.queries import draft_review_sla

        now = timezone.now()
        # Given: 결정 시각이 없는 레거시 승인 건과 반려 건
        legacy_approved = make_draft(
            review_status=EventDraft.ReviewStatus.APPROVED,
            approved_at=None,
        )
        EventDraft.objects.filter(pk=legacy_approved.pk).update(created_at=now - timedelta(days=1))
        legacy_rejected = make_draft(
            review_status=EventDraft.ReviewStatus.REJECTED,
            rejected_at=None,
        )
        EventDraft.objects.filter(pk=legacy_rejected.pk).update(created_at=now - timedelta(days=1))

        # When: SLA를 조회하면
        result = draft_review_sla(now=now)

        # Then: 결정 시각이 없는 건은 창 집계에서 제외되고 대기 건도 아니다
        assert result["decided_count"] == 0
        assert result["rejected_count"] == 0
        assert result["avg_handling"] is None
        assert result["rejection_rate"] is None
        assert result["pending_count"] == 0


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

    def test_활성_소스가_인스타뿐이면_서버_수집_대상_존재_여부는_거짓이다(self):
        from drafts.queries import enabled_draft_sources_exist

        DraftSource.objects.create(
            name="instagram-source",
            url="https://example.com/instagram-feed/",
            source_type="instagram",
            enabled=True,
        )

        assert enabled_draft_sources_exist() is False

    def test_손상된_source_type만_활성이어도_서버_수집_대상_존재_여부는_참이다(self):
        from drafts.queries import enabled_draft_sources_exist

        DraftSource.objects.create(
            name="corrupted-source",
            url="https://example.com/atom-feed/",
            source_type="atom",
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


@pytest.mark.django_db
class TestRecentDiscoveryRuns:
    """S8 대시보드 상세 표시용 계약: 행사 생성/제외/실패 건수와 결과별 표시 행."""

    def test_후보와_행사_드래프트가_함께_있어도_조인_곱으로_건수가_부풀지_않는다(self):
        """candidates와 events(드래프트)를 한 쿼리에서 Count하면 조인 곱이 생긴다 —
        distinct 처리가 없으면 이 테스트가 promoted_count·events_created를 실제보다
        크게 계산해 실패한다."""
        from drafts.queries import recent_discovery_runs

        run = SourceDiscoveryRun.objects.create(status=SourceDiscoveryRun.Status.SUCCEEDED)
        SourceCandidate.objects.create(
            run=run,
            name="후보1",
            url="https://example.com/c1",
            source_type="html",
            sample_url="https://example.com/c1/sample",
            status=SourceCandidate.Status.PROMOTED,
        )
        SourceCandidate.objects.create(
            run=run,
            name="후보2",
            url="https://example.com/c2",
            source_type="html",
            sample_url="https://example.com/c2/sample",
            status=SourceCandidate.Status.FAILED,
        )
        EventDraft.objects.create(source_url="https://example.com/e1", discovery_run=run)
        EventDraft.objects.create(source_url="https://example.com/e2", discovery_run=run)

        rows = recent_discovery_runs()

        row = next(r for r in rows if r["run"].pk == run.pk)
        assert row["promoted_count"] == 1
        assert row["failed_count"] == 1
        assert row["events_created"] == 2

    def test_결과_목록이_비어있는_옛_실행은_제외_실패_건수가_None이다(self):
        from drafts.queries import recent_discovery_runs

        old_run = SourceDiscoveryRun.objects.create(
            status=SourceDiscoveryRun.Status.SUCCEEDED,
            event_outcomes=[],
            events_excluded=3,
            events_failed=2,
        )

        rows = recent_discovery_runs()

        row = next(r for r in rows if r["run"].pk == old_run.pk)
        assert row["events_excluded"] is None
        assert row["events_failed"] is None

    def test_결과_목록이_있는_실행은_제외_실패_건수를_필드값_그대로_보여준다(self):
        from drafts.queries import recent_discovery_runs

        run = SourceDiscoveryRun.objects.create(
            status=SourceDiscoveryRun.Status.SUCCEEDED,
            events_excluded=2,
            events_failed=1,
            event_outcomes=[
                {"url": "https://example.com/x1", "outcome": "excluded", "reason": "ended"},
            ],
        )

        rows = recent_discovery_runs()

        row = next(r for r in rows if r["run"].pk == run.pk)
        assert row["events_excluded"] == 2
        assert row["events_failed"] == 1

    def test_결과_행이_호스트_경로_배지_사유라벨을_계산한다(self):
        from drafts.queries import recent_discovery_runs

        run = SourceDiscoveryRun.objects.create(
            status=SourceDiscoveryRun.Status.SUCCEEDED,
            event_outcomes=[
                {
                    "url": "https://example.com/events/1?ref=abc#frag",
                    "outcome": "created",
                    "reason": "",
                },
                {
                    "url": "https://example.com/events/2",
                    "outcome": "duplicate",
                    "reason": "",
                },
                {
                    "url": "https://example.com/events/3",
                    "outcome": "excluded",
                    "reason": "overseas",
                },
                {
                    "url": "https://example.com/events/4",
                    "outcome": "failed",
                    "reason": "fetch_error",
                },
                {
                    "url": "https://example.com/events/5",
                    "outcome": "skipped",
                    "reason": "known_url",
                },
                {
                    "url": "https://example.com/events/6",
                    "outcome": "excluded",
                    "reason": "not_a_real_reason",
                },
            ],
        )

        rows = recent_discovery_runs()

        row = next(r for r in rows if r["run"].pk == run.pk)
        outcome_rows = row["outcome_rows"]
        assert len(outcome_rows) == 6

        created_row = outcome_rows[0]
        assert created_row["display_url"] == "example.com/events/1"
        assert created_row["outcome"] == "created"
        assert created_row["outcome_label"] == "생성됨"
        assert created_row["tone"] == "ok"
        assert created_row["reason_label"] == ""

        duplicate_row = outcome_rows[1]
        assert duplicate_row["outcome_label"] == "중복"
        assert duplicate_row["tone"] == "disabled"

        excluded_row = outcome_rows[2]
        assert excluded_row["outcome_label"] == "제외"
        assert excluded_row["tone"] == "disabled"
        assert excluded_row["reason_label"] == "해외 행사"

        failed_row = outcome_rows[3]
        assert failed_row["outcome_label"] == "실패"
        assert failed_row["tone"] == "error"
        assert failed_row["reason_label"] == "가져오기 오류"

        skipped_row = outcome_rows[4]
        assert skipped_row["outcome_label"] == "건너뜀"
        assert skipped_row["tone"] == "disabled"
        assert skipped_row["reason_label"] == "이미 등록된 URL"

        unknown_reason_row = outcome_rows[5]
        assert unknown_reason_row["reason_label"] == "알 수 없음"

    def test_url에_계정_정보가_섞여있어도_화면에_노출하지_않는다(self):
        """urlsplit의 netloc은 user:pass@host 형태를 그대로 담으므로, hostname만
        써서 계정 정보가 상세 표에 노출되지 않게 고정한다."""
        from drafts.queries import recent_discovery_runs

        run = SourceDiscoveryRun.objects.create(
            status=SourceDiscoveryRun.Status.SUCCEEDED,
            event_outcomes=[
                {
                    "url": "https://user:secret@example.com/e/1?x=1",
                    "outcome": "created",
                    "reason": "",
                },
            ],
        )

        rows = recent_discovery_runs()

        row = next(r for r in rows if r["run"].pk == run.pk)
        display_url = row["outcome_rows"][0]["display_url"]
        assert display_url == "example.com/e/1"
        assert "secret" not in display_url

    def test_사유_라벨_사전은_허용된_모든_사유값을_덮는다(self):
        """EVENT_OUTCOME_REASONS 허용 목록에 새 사유가 추가되면 라벨 사전도
        같이 갱신해야 한다는 것을 강제한다."""
        from drafts.queries import EVENT_OUTCOME_REASON_LABELS

        all_reasons = {
            reason
            for reasons in EVENT_OUTCOME_REASONS.values()
            for reason in reasons
            if reason
        }

        assert all_reasons <= set(EVENT_OUTCOME_REASON_LABELS.keys())

    def test_쿼리_수가_실행_건수와_무관하게_고정된다(self, django_assert_num_queries):
        """실행 3건 각각 후보·드래프트·결과 목록을 갖고 있어도 N+1 없이 1쿼리로
        끝나야 한다 — annotate 집계 결과와 event_outcomes JSON은 같은 행에서
        오므로 추가 쿼리가 필요 없다."""
        from drafts.queries import recent_discovery_runs

        for i in range(3):
            run = SourceDiscoveryRun.objects.create(
                status=SourceDiscoveryRun.Status.SUCCEEDED,
                event_outcomes=[
                    {"url": f"https://example.com/r{i}/1", "outcome": "created", "reason": ""},
                ],
            )
            SourceCandidate.objects.create(
                run=run,
                name=f"후보{i}",
                url=f"https://example.com/r{i}/c1",
                source_type="html",
                sample_url=f"https://example.com/r{i}/c1/sample",
                status=SourceCandidate.Status.PROMOTED,
            )
            EventDraft.objects.create(source_url=f"https://example.com/r{i}/e1", discovery_run=run)

        with django_assert_num_queries(1):
            rows = recent_discovery_runs()
            for row in rows:
                # outcome_rows 계산이 run.event_outcomes(이미 로딩된 필드)만
                # 쓰는지 강제로 소비해 확인한다.
                list(row["outcome_rows"])
