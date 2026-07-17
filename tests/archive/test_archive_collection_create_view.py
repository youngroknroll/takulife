"""Tests for the collection-item create page (core.views.archive_collection_item_create).

Behavior under test (collection domain design plan §4 PR-C5b-2, CP-C1~C9):
- /collection/new/ is login-gated.
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

pytestmark = pytest.mark.web


@pytest.mark.django_db
class TestArchiveCollectionCreateViewAuth:
    def test_로그인한_사용자가_등록_페이지에_접근하면_페이지가_렌더링된다(self, user_client):
        _, client = user_client()

        resp = client.get("/collection/new/")

        assert resp.status_code == 200
        assert "core/archive/collection_create.html" in [t.name for t in resp.templates]

    def test_비로그인_사용자가_등록_페이지에_접근하면_로그인으로_리다이렉트된다(self, client):
        resp = client.get("/collection/new/")

        assert resp.status_code == 302
        assert "/accounts/login" in resp.url


@pytest.mark.django_db
class TestArchiveCollectionCreateSelectableVisitRecords:
    def test_선택_가능한_방문_기록이_본인_소유로만_한정된다(
        self, user_client, make_user, make_event, make_visit
    ):
        user, client = user_client()
        other = make_user()
        mine = make_visit(user, event=make_event(title="내 방문"), visited_on="2026-01-01")
        make_visit(other, event=make_event(title="남의 방문"), visited_on="2026-01-02")

        resp = client.get("/collection/new/")

        records = list(resp.context["selectable_visit_records"])
        assert records == [mine]


@pytest.mark.django_db
class TestArchiveCollectionCreatePreselect:
    def test_본인_방문_기록을_지정하면_해당_기록으로_선택이_고정된다(self, user_client, make_event, make_visit):
        user, client = user_client()
        event = make_event(title="다녀온 행사")
        record = make_visit(user, event=event, visited_on="2026-05-01")

        resp = client.get(f"/collection/new/?visit_record={record.id}")

        assert resp.context["preselect"] == {
            "id": record.id,
            "label": "다녀온 행사 · 2026-05-01",
        }
        assert f'value="{record.id}"'.encode() in resp.content

    def test_다른_사용자의_방문_기록을_지정하면_선택_고정이_무시된다(
        self, user_client, make_user, make_event, make_visit
    ):
        _, client = user_client()
        other = make_user()
        other_record = make_visit(
            other, event=make_event(title="남의 행사"), visited_on="2026-05-01"
        )

        resp = client.get(f"/collection/new/?visit_record={other_record.id}")

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
        ids=[
            "문자와_숫자_혼합",
            "영문자만",
            "위첨자_숫자",
            "DB_정수_범위_초과",
            "빈_문자열",
        ],
    )
    def test_방문_기록_값이_잘못되면_선택_고정이_해제된다(self, user_client, raw):
        _, client = user_client()

        resp = client.get(f"/collection/new/?visit_record={raw}")

        assert resp.status_code == 200
        assert resp.context["preselect"] is None

    def test_방문_기록_지정이_없으면_선택_목록이_유지된다(self, user_client):
        _, client = user_client()

        resp = client.get("/collection/new/")

        assert resp.context["preselect"] is None
        assert "selectable_visit_records" in resp.context


@pytest.mark.django_db
class TestArchiveCollectionCreateItemTypeDatalist:
    def test_굿즈_종류_입력에_어휘_7종이_데이터리스트로_제공된다(self, user_client):
        _, client = user_client()

        resp = client.get("/collection/new/")
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

    def test_공개_범위_필드는_등록_폼에_노출되지_않는다(self, user_client):
        _, client = user_client()

        resp = client.get("/collection/new/")

        assert b'name="visibility"' not in resp.content

    def test_행사_선택_필드는_등록_폼에_노출되지_않는다(self, user_client):
        _, client = user_client()

        resp = client.get("/collection/new/")

        assert b'name="event"' not in resp.content
