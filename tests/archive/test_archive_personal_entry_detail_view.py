"""Tests for the read-only personal-entry (unofficial place) detail page
(core.views, URL name "archive-personal-entry-detail-page").

The page shows one PersonalEntry's title and, separately, its current
official-submission status via `resp.context["is_submitted"]`. The page is
owner-scoped: a non-owner request 404s and an anonymous request redirects
to login.
"""
from datetime import datetime

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from archive.models import PersonalEntry, UserEventStatus

pytestmark = pytest.mark.web


@pytest.mark.django_db
class TestArchivePersonalEntryDetailView:
    def test_본인_소유_비공식_장소의_상세_페이지를_열면_200과_함께_제목이_표시된다(
        self, user_client, make_entry
    ):
        # PD-1
        user, client = user_client()
        entry = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="숨겨진 골목 소품샵")

        resp = client.get(reverse("archive-personal-entry-detail-page", args=[entry.pk]))

        assert resp.status_code == 200
        assert "숨겨진 골목 소품샵".encode() in resp.content

    def test_타인_소유_비공식_장소의_상세_페이지에_접근하면_404가_반환된다(
        self, make_user, user_client, make_entry
    ):
        # PD-2
        owner = make_user()
        entry = make_entry(owner, kind=PersonalEntry.Kind.PLACE, title="소유자 전용 비공식 장소")
        attacker, client = user_client()

        resp = client.get(reverse("archive-personal-entry-detail-page", args=[entry.pk]))

        assert resp.status_code == 404

    def test_비로그인_사용자가_비공식_장소_상세_페이지를_열면_로그인_페이지로_리다이렉트된다(
        self, make_user, make_entry
    ):
        # PD-3
        entry = make_entry(
            make_user(), kind=PersonalEntry.Kind.PLACE, title="비로그인 접근 비공식 장소"
        )

        resp = Client().get(reverse("archive-personal-entry-detail-page", args=[entry.pk]))

        assert resp.status_code == 302
        assert "/accounts/login" in resp.url


@pytest.mark.django_db
class TestArchivePersonalEntryDetailPromotionStatus:
    @pytest.mark.parametrize(
        ("promotion_status", "expected_is_submitted"),
        [
            (PersonalEntry.PromotionStatus.NONE, False),
            (PersonalEntry.PromotionStatus.SUBMITTED, True),
        ],
        ids=["미제보", "제보됨"],
    )
    def test_상황에서_공식_제보_상태를_열람하면_현재_제보_완료_여부가_그대로_표시된다(
        self, user_client, make_entry, promotion_status, expected_is_submitted
    ):
        # PD-8
        user, client = user_client()
        entry = make_entry(
            user,
            kind=PersonalEntry.Kind.PLACE,
            title="제보 상태 확인용 장소",
            promotion_status=promotion_status,
        )

        resp = client.get(reverse("archive-personal-entry-detail-page", args=[entry.pk]))

        assert resp.context["is_submitted"] is expected_is_submitted


@pytest.mark.django_db
class TestArchivePersonalEntryDetailRecordInfo:
    def test_등록일과_마지막_수정일이_서로_다르면_각각_올바른_라벨에_표시된다(
        self, user_client, make_entry
    ):
        # PD-6
        user, client = user_client()
        entry = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="기록 정보 확인용 장소")
        PersonalEntry.objects.filter(pk=entry.pk).update(
            created_at=timezone.make_aware(datetime(2026, 3, 5)),
            updated_at=timezone.make_aware(datetime(2026, 6, 18)),
        )

        resp = client.get(reverse("archive-personal-entry-detail-page", args=[entry.pk]))

        entry.refresh_from_db()
        record_info_rows = resp.context["record_info_rows"]
        rows_by_label = {row["label"]: row["value"] for row in record_info_rows}
        assert rows_by_label["등록일"] == entry.created_at
        assert rows_by_label["마지막 수정"] == entry.updated_at


@pytest.mark.django_db
class TestArchivePersonalEntryDetailInterestAndStatus:
    """두 케이스의 Given이 크게 다르다: 있는 케이스는 "대상 항목의 id로 정확히 조회하는가"를
    증명하기 위한 미끼(다른 PersonalEntry에 걸린 다른 찜·다른 상태)가 필요하고, 없는 케이스는
    항목 하나만 있으면 된다. 파라미터화로 두 Given을 하나의 표에 욱여넣으면 미끼의 존재
    이유가 표 뒤로 숨어버려 DAMP를 해친다고 판단해 별도 테스트로 분리했다.

    미끼 하나로는 부족하다: 미끼가 대상보다 나중에 생성되면 정렬 없는 쿼리의 순회가 우연히
    대상을 먼저 내놓아, 조회 키(entry.id)를 무시하고 아무 값이나 집는 구현도 통과한다(뮤테이션
    테스트로 실측). PD-7b는 같은 사용자의 두 항목을 모두 조회해 각자 자기 값만 보이는지
    확인함으로써 쿼리 순회 순서와 무관하게 키-무시 구현을 잡는다.
    """

    def test_본인의_찜과_상태가_있으면_그_현재값이_상세_페이지_컨텍스트에_반영된다(
        self, user_client, make_entry, make_interest, make_status
    ):
        # PD-7 (있는 케이스)
        user, client = user_client()
        entry = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="찜과 상태 확인용 장소")
        decoy_entry = make_entry(
            user, kind=PersonalEntry.Kind.PLACE, title="미끼 비공식 장소"
        )
        # 미끼: 다른 항목에 다른 찜·다른 상태를 먼저 걸어, 뷰가 딕셔너리의 아무 값이나
        # 집어도 통과하지 않도록 만든다.
        make_interest(user, personal_entry=decoy_entry)
        make_status(user, personal_entry=decoy_entry, status=UserEventStatus.Status.VISITED)
        interest = make_interest(user, personal_entry=entry)
        status = make_status(user, personal_entry=entry, status=UserEventStatus.Status.PLANNED)

        resp = client.get(reverse("archive-personal-entry-detail-page", args=[entry.pk]))

        assert resp.context["interest_id"] == interest.pk
        assert resp.context["status_slug"] == UserEventStatus.Status.PLANNED
        assert resp.context["status_id"] == status.pk

    def test_본인의_찜과_상태가_없으면_찜_id는_없고_상태_슬러그는_빈_값으로_반영된다(
        self, user_client, make_entry
    ):
        # PD-7 (없는 케이스)
        user, client = user_client()
        entry = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="찜과 상태 미보유 장소")

        resp = client.get(reverse("archive-personal-entry-detail-page", args=[entry.pk]))

        assert resp.context["interest_id"] is None
        assert resp.context["status_slug"] == ""

    def test_같은_사용자의_서로_다른_항목_각각의_상세는_자기_항목의_찜과_상태만_보여준다(
        self, user_client, make_entry, make_interest, make_status
    ):
        """PD-7b: 조회 키(entry.id)를 무시하고 맵의 아무 값이나 집는 구현은 두 항목 중 최소
        하나에서 반드시 틀린다는 사실을, 쿼리 순회 순서에 기대지 않고 증명한다. PD-7의
        "있는 케이스"는 대상 항목 하나만 검증했는데, 그 대상을 미끼보다 먼저 만들었더니
        우연히 정렬되지 않은 쿼리의 첫 값이 대상과 일치해 `next(iter(map.values()))`
        같은 키-무시 구현도 통과시켰다(뮤테이션 테스트로 실측). 두 항목의 상세를 모두
        요청해 각자 자기 값만 보이는지 확인하면, 두 항목이 같은 딕셔너리를 조회하므로
        "첫 값"이 무엇이든 둘 중 하나는 반드시 어긋난다 — 정렬 순서와 무관하다.
        """
        user, client = user_client()
        entry_a = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="항목 A")
        entry_b = make_entry(user, kind=PersonalEntry.Kind.PLACE, title="항목 B")
        interest_a = make_interest(user, personal_entry=entry_a)
        interest_b = make_interest(user, personal_entry=entry_b)
        status_a = make_status(user, personal_entry=entry_a, status=UserEventStatus.Status.PLANNED)
        status_b = make_status(user, personal_entry=entry_b, status=UserEventStatus.Status.VISITED)

        resp_a = client.get(reverse("archive-personal-entry-detail-page", args=[entry_a.pk]))
        resp_b = client.get(reverse("archive-personal-entry-detail-page", args=[entry_b.pk]))

        assert resp_a.context["interest_id"] == interest_a.pk
        assert resp_a.context["status_slug"] == UserEventStatus.Status.PLANNED
        assert resp_a.context["status_id"] == status_a.pk
        assert resp_b.context["interest_id"] == interest_b.pk
        assert resp_b.context["status_slug"] == UserEventStatus.Status.VISITED
        assert resp_b.context["status_id"] == status_b.pk
