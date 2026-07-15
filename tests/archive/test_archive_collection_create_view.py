"""Tests for the collection-item create page (core.views.archive_collection_item_create).

Behavior under test (collection domain design plan §4 PR-C5b-2, CP-C1~C9):
- /archive/collection/new/ is login-gated.
- selectable_visit_records lists ONLY the requester's own visit records
  (list_user_visit_records(request.user), unfiltered).
- ?visit_record=<id> preselects and locks the form to that visit record when
  it exists and belongs to the requester; any other value (malformed,
  missing, or another user's id) falls back to the selectable dropdown
  instead of a 500 — mirrors _parse_visit_preselect's isascii/isdigit/length
  guard (visit_create.html's ?subject= precedent).
- item_type is a free-text input suggested via a <datalist> of the 7
  core.vocab.COLLECTION_ITEM_TYPE options.
- `visibility` (reserved for the future trade opt-in gate) and any
  `name="event"` control (event is server-synced from visit_record, never
  user-selected — collection domain design plan §3-1) are never rendered.
"""
import pytest

from core.vocab import COLLECTION_ITEM_TYPE


@pytest.mark.django_db
class TestArchiveCollectionCreateViewAuth:
    def test_authenticated_user_gets_200(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/collection/new/")

        assert resp.status_code == 200
        assert "core/archive/collection_create.html" in [t.name for t in resp.templates]

    def test_anonymous_user_redirected_to_login(self, client):
        resp = client.get("/archive/collection/new/")

        assert resp.status_code == 302
        assert "/accounts/login" in resp.url


@pytest.mark.django_db
class TestArchiveCollectionCreateSelectableVisitRecords:
    def test_selectable_visit_records_owner_scoped(
        self, user_client, make_user, make_event, make_visit
    ):
        user, client = user_client()
        other = make_user()
        mine = make_visit(user, event=make_event(title="내 방문"), visited_on="2026-01-01")
        make_visit(other, event=make_event(title="남의 방문"), visited_on="2026-01-02")

        resp = client.get("/archive/collection/new/")

        records = list(resp.context["selectable_visit_records"])
        assert records == [mine]


@pytest.mark.django_db
class TestArchiveCollectionCreatePreselect:
    def test_own_visit_record_locks_subject(self, user_client, make_event, make_visit):
        user, client = user_client()
        event = make_event(title="다녀온 행사")
        record = make_visit(user, event=event, visited_on="2026-05-01")

        resp = client.get(f"/archive/collection/new/?visit_record={record.id}")

        assert resp.context["preselect"] == {
            "id": record.id,
            "label": "다녀온 행사 · 2026-05-01",
        }
        assert f'value="{record.id}"'.encode() in resp.content

    def test_other_users_visit_record_ignored(
        self, user_client, make_user, make_event, make_visit
    ):
        _, client = user_client()
        other = make_user()
        other_record = make_visit(
            other, event=make_event(title="남의 행사"), visited_on="2026-05-01"
        )

        resp = client.get(f"/archive/collection/new/?visit_record={other_record.id}")

        assert resp.status_code == 200
        assert resp.context["preselect"] is None

    @pytest.mark.parametrize(
        "raw",
        [
            "garbage",
            "abc",
            "²",  # superscript two — isdigit() True, int() raises
            "9" * 30,  # past the DB integer range
            "",
        ],
    )
    def test_malformed_visit_record_param_falls_back(self, user_client, raw):
        _, client = user_client()

        resp = client.get(f"/archive/collection/new/?visit_record={raw}")

        assert resp.status_code == 200
        assert resp.context["preselect"] is None

    def test_no_visit_record_param_keeps_dropdown(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/collection/new/")

        assert resp.context["preselect"] is None
        assert "selectable_visit_records" in resp.context


@pytest.mark.django_db
class TestArchiveCollectionCreateItemTypeDatalist:
    def test_datalist_has_seven_vocab_options(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/collection/new/")
        content = resp.content.decode()

        assert 'id="collection-item-type-options"' in content
        for _, label in COLLECTION_ITEM_TYPE:
            assert f'<option value="{label}">' in content
        start = content.index('id="collection-item-type-options"')
        end = content.index("</datalist>", start)
        assert content[start:end].count("<option") == 7


@pytest.mark.django_db
class TestArchiveCollectionCreateHiddenFields:
    """visibility and event must never be exposed as form controls — event is
    always server-synced from visit_record (§3-1), and visibility is reserved
    for the future trade opt-in gate (no exposure until Stage 4)."""

    def test_visibility_field_never_rendered(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/collection/new/")

        assert b'name="visibility"' not in resp.content

    def test_event_control_never_rendered(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/collection/new/")

        assert b'name="event"' not in resp.content
