"""Tests for the visit-record edit page (core.views.archive_visit_edit).

The page is owner-scoped and pre-fills the record's editable fields. The subject
is shown read-only; editing happens via the PATCH/photo APIs from visit_edit.js.
"""
import pytest
from django.test import Client

from archive.models import VisitRecord


@pytest.mark.django_db
class TestArchiveVisitEditView:
    def _record(self, user, event, **kwargs):
        return VisitRecord.objects.create(
            user=user, event=event, visited_on="2026-05-26", **kwargs
        )

    def test_owner_gets_edit_page(self, make_user, make_event):
        user = make_user()
        record = self._record(user, make_event(title="My event"), short_review="memo")

        client = Client()
        client.force_login(user)
        resp = client.get(f"/archive/visits/{record.id}/edit/")

        assert resp.status_code == 200
        assert "core/archive_visit_edit.html" in [t.name for t in resp.templates]
        assert resp.context["record_id"] == record.id
        assert resp.context["subject"]["title"] == "My event"
        assert str(resp.context["visited_on"]) == "2026-05-26"
        assert resp.context["short_review"] == "memo"
        assert list(resp.context["photos"]) == []

    def test_non_owner_record_returns_404(self, make_user, make_event):
        owner = make_user()
        attacker = make_user()
        record = self._record(owner, make_event())

        client = Client()
        client.force_login(attacker)
        resp = client.get(f"/archive/visits/{record.id}/edit/")

        assert resp.status_code == 404

    def test_anonymous_redirected_to_login(self, make_user, make_event):
        record = self._record(make_user(), make_event())

        resp = Client().get(f"/archive/visits/{record.id}/edit/")

        assert resp.status_code == 302
        assert "/accounts/login" in resp.url
