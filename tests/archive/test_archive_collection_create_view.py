"""굿즈 등록 페이지(core.views.archive_collection_item_create) 테스트.

검증 대상 동작(컬렉션 도메인 설계 계획 §4 PR-C5b-2, CP-C1~C9):
- /collection/new/ 는 로그인 필수.
- selectable_visit_records 는 요청자 본인의 방문 기록만 나열한다
  (list_user_visit_records(request.user), 무필터).
- ?visit_record=<id> 는 그 기록이 존재하고 요청자 소유일 때만 폼을 그 값으로
  고정한다; 그 외 값(형식 오류·존재하지 않음·타인 소유)은 500 대신 선택
  드롭다운으로 폴백한다 — _parse_visit_preselect의 isascii/isdigit/length
  가드를 따른다(visit_create.html의 ?subject= 선례).
- item_type 은 자유 텍스트 입력이며 core.vocab.COLLECTION_ITEM_TYPE 7종을
  추천 칩(button.collection-form-type-chip[data-type-label])으로 제안한다
  — <datalist> 방식에서 칩 방식으로 전환됐다(삭제가 아니라 커버리지 이동).
- `visibility`(향후 교환 opt-in 게이트용)와 `name="event"` 컨트롤(event는
  visit_record에서 서버가 동기화하며 사용자가 직접 선택하지 않음 — 컬렉션
  도메인 설계 계획 §3-1)은 절대 렌더되지 않는다.
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
            "²",  # 위첨자 2 — isdigit()는 True인데 int()는 실패한다
            "9" * 30,  # DB 정수 범위를 넘는다
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
class TestArchiveCollectionCreateItemTypeChips:
    def test_굿즈_종류_입력에_어휘_7종이_추천_칩으로_제공된다(self, user_client):
        _, client = user_client()

        resp = client.get("/collection/new/")
        content = resp.content.decode()

        assert 'class="collection-form-type-chip"' in content
        for _, label in COLLECTION_ITEM_TYPE:
            assert f'data-type-label="{label}"' in content
        assert content.count('class="collection-form-type-chip"') == 7

        assert 'name="item_type"' in content
        assert 'id="collection-item-type-options"' not in content
        assert "<datalist" not in content


@pytest.mark.django_db
class TestArchiveCollectionCreateHiddenFields:
    """visibility·event는 폼 컨트롤로 절대 노출되지 않는다 — event는 항상
    visit_record에서 서버가 동기화하며(§3-1), visibility는 4단계 전까지
    노출하지 않는 향후 교환 opt-in 게이트용이다."""

    def test_공개_범위_필드는_등록_폼에_노출되지_않는다(self, user_client):
        _, client = user_client()

        resp = client.get("/collection/new/")

        assert b'name="visibility"' not in resp.content

    def test_행사_선택_필드는_등록_폼에_노출되지_않는다(self, user_client):
        _, client = user_client()

        resp = client.get("/collection/new/")

        assert b'name="event"' not in resp.content
