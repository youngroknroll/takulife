"""Tests for the read-only personal-entry (unofficial place) detail page
(core.views, URL name "archive-personal-entry-detail-page").

The page shows one PersonalEntry's title.
"""
import pytest
from django.urls import reverse

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
