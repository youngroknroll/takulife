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

from archive.models import PersonalEntry

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
