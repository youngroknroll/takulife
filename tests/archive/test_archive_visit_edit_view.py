"""Tests for the visit-record edit page (core.views.archive_visit_edit).

The page is owner-scoped and pre-fills the record's editable fields. The subject
is shown read-only; editing happens via the PATCH/photo APIs from visit_edit.js.
"""
import pytest
from django.test import Client


@pytest.mark.django_db
class TestArchiveVisitEditView:
    def test_owner_gets_edit_page(self, make_user, make_event, make_visit):
        user = make_user()
        record = make_visit(
            user, event=make_event(title="My event"), visited_on="2026-05-26", short_review="memo"
        )

        client = Client()
        client.force_login(user)
        resp = client.get(f"/archive/visits/{record.id}/edit/")

        assert resp.status_code == 200
        assert "core/archive/visit_edit.html" in [t.name for t in resp.templates]
        assert resp.context["record_id"] == record.id
        assert resp.context["subject"]["title"] == "My event"
        assert str(resp.context["visited_on"]) == "2026-05-26"
        assert resp.context["short_review"] == "memo"
        assert list(resp.context["photos"]) == []

    def test_non_owner_record_returns_404(self, make_user, make_event, make_visit):
        owner = make_user()
        attacker = make_user()
        record = make_visit(owner, event=make_event(), visited_on="2026-05-26")

        client = Client()
        client.force_login(attacker)
        resp = client.get(f"/archive/visits/{record.id}/edit/")

        assert resp.status_code == 404

    def test_anonymous_redirected_to_login(self, make_user, make_event, make_visit):
        record = make_visit(make_user(), event=make_event(), visited_on="2026-05-26")

        resp = Client().get(f"/archive/visits/{record.id}/edit/")

        assert resp.status_code == 302
        assert "/accounts/login" in resp.url
