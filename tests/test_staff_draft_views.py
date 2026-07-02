"""Tests for the staff-only draft HTML views (event_drafts / event_draft_detail).

Existing tests only exercised the staff *guard* (redirect / not-found). These
cover the populated paths: the list row loop and the detail label rendering.
"""
import pytest
from django.test import Client

from drafts.models import EventDraft


def _staff_client(make_user):
    user = make_user(is_staff=True)
    client = Client()
    client.force_login(user)
    return client


@pytest.mark.django_db
class TestEventDraftsListView:
    def test_list_renders_draft_rows(self, make_user):
        EventDraft.objects.create(
            source_url="https://example.com/a",
            extracted_title="드래프트 A",
            extracted_category="popup_store",
        )
        EventDraft.objects.create(
            source_url="https://example.com/b", extracted_title="드래프트 B"
        )

        resp = _staff_client(make_user).get("/staff/drafts/")

        assert resp.status_code == 200
        body = resp.content.decode()
        assert "드래프트 A" in body
        assert "드래프트 B" in body


@pytest.mark.django_db
class TestEventDraftDetailView:
    def test_existing_draft_renders_with_labels(self, make_user):
        draft = EventDraft.objects.create(
            source_url="https://example.com/c",
            extracted_title="상세 드래프트",
            extracted_category="popup_store",
            extracted_region="seoul",
        )

        resp = _staff_client(make_user).get(f"/staff/drafts/{draft.id}/")

        assert resp.status_code == 200
        assert resp.context["draft"] == draft
        assert resp.context["is_pending"] is True
        # Slugs resolved to human labels.
        assert resp.context["category_label"] == "팝업스토어"
        assert resp.context["region_label"] == "서울"

    def test_missing_draft_shows_not_found_notice(self, make_user):
        resp = _staff_client(make_user).get("/staff/drafts/999999/")

        assert resp.status_code == 200
        assert resp.context["draft_not_found"] is True
