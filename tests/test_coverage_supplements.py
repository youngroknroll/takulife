"""Targeted tests for small uncovered branches across the apps.

Each test closes a specific previously-uncovered line: model __str__, a
queryset status arm, a query filter arm, serializer/​service guard branches,
and a few API error/redirect paths.
"""
import datetime

import pytest
from django.test import Client

from archive.models import PersonalEntry, UserEventStatus, VisitRecord
from archive.queries import list_user_visit_records
from archive.serializers import PersonalEntrySerializer
from drafts.models import EventDraft
from drafts.services import create_draft_from_url
from events.models import Event


@pytest.mark.django_db
class TestModelStr:
    def test_personal_entry_str(self):
        entry = PersonalEntry(title="비공식 카페")
        assert str(entry) == "비공식 카페"

    def test_event_draft_str(self):
        draft = EventDraft(source_url="https://example.com/x")
        assert str(draft) == "https://example.com/x"

    def test_event_str(self):
        assert str(Event(title="행사 제목")) == "행사 제목"


@pytest.mark.django_db
class TestQuerysetAndQueryArms:
    def test_with_public_status_ended(self, make_event):
        today = datetime.date(2026, 7, 1)
        ended = make_event(
            title="끝난 행사",
            start_date=today - datetime.timedelta(days=10),
            end_date=today - datetime.timedelta(days=1),
        )
        ongoing = make_event(
            title="진행 행사",
            start_date=today - datetime.timedelta(days=1),
            end_date=today + datetime.timedelta(days=5),
        )

        result = Event.objects.published().with_public_status("ended", today=today)

        assert ended in result
        assert ongoing not in result

    def test_with_public_status_unknown_returns_unfiltered(self, make_event):
        today = datetime.date(2026, 7, 1)
        make_event(title="아무 행사")
        qs = Event.objects.published()

        # Unrecognised status falls through every arm to `return self`.
        assert list(qs.with_public_status("nonsense", today=today)) == list(qs)

    def test_list_user_visit_records_official_only(self, make_event, make_user):
        user = make_user()
        event = make_event(title="공식 방문")
        entry = PersonalEntry.objects.create(
            user=user, kind=PersonalEntry.Kind.PLACE, title="비공식 방문"
        )
        VisitRecord.objects.create(user=user, event=event, visited_on="2026-01-01")
        VisitRecord.objects.create(user=user, personal_entry=entry, visited_on="2026-01-02")

        official = list(list_user_visit_records(user, official=True))

        assert all(r.event_id is not None for r in official)
        assert len(official) == 1


class TestSerializerGuard:
    def test_validate_image_passes_empty_through(self):
        # The optional image guard returns empty values untouched (no upload).
        assert PersonalEntrySerializer().validate_image("") == ""
        assert PersonalEntrySerializer().validate_image(None) is None


@pytest.mark.django_db
class TestServiceGuards:
    def test_create_draft_from_invalid_url_raises_value_error(self):
        with pytest.raises(ValueError):
            create_draft_from_url(source_url="ftp://not-allowed/")


@pytest.mark.django_db
class TestStatusUpdateNoTransition:
    def test_patch_without_status_saves_without_transition(self, make_event, make_user):
        user = make_user()
        event = make_event(title="상태 전환")
        status_obj = UserEventStatus.objects.create(
            user=user, event=event, status="planned"
        )

        client = Client()
        client.force_login(user)
        # No status in the payload → validated status is None → the plain save()
        # arm (no transition) runs.
        resp = client.patch(
            f"/api/user-event-statuses/{status_obj.id}/",
            data={},
            content_type="application/json",
        )

        assert resp.status_code == 200
        status_obj.refresh_from_db()
        assert status_obj.status == "planned"


@pytest.mark.django_db
class TestPromotionDuplicate:
    def test_promote_with_existing_draft_url_returns_field_error(
        self, make_user
    ):
        user = make_user()
        entry = PersonalEntry.objects.create(
            user=user, kind=PersonalEntry.Kind.PLACE, title="제보 대상"
        )
        # A draft already owns this official URL → promotion is a duplicate.
        EventDraft.objects.create(source_url="https://dup.example.com/")

        client = Client()
        client.force_login(user)
        resp = client.post(
            f"/api/personal-entries/{entry.id}/promote/",
            data={"official_url": "https://dup.example.com/"},
            content_type="application/json",
        )

        assert resp.status_code == 400
        assert "official_url" in resp.json()


@pytest.mark.django_db
class TestRegisterRedirect:
    def test_register_redirects_to_safe_next(self):
        resp = Client().post(
            "/accounts/register/?next=/archive/visits/",
            data={
                "username": "newcomer",
                "password1": "Str0ng-Pass-99",
                "password2": "Str0ng-Pass-99",
            },
        )
        assert resp.status_code == 302
        assert resp["Location"] == "/archive/visits/"
