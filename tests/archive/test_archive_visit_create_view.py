"""방문 기록 작성 전용 페이지(web.views.archive_visit_create) 테스트.

/archive/visits/new/ 는 기존 인라인 폼과 같은 대상 선택지(본인 참석예정 행사 +
본인 직접 등록 항목)를 보여주며 로그인이 필요하다.
"""

from django.test import Client
import pytest

from archive.models import UserEventStatus

pytestmark = pytest.mark.web


@pytest.mark.django_db
class TestArchiveVisitCreateView:
    def test_로그인한_사용자가_방문_기록_작성_페이지에_접근하면_작성_페이지가_렌더링된다(
        self, make_user
    ):
        client = Client()
        client.force_login(make_user())

        resp = client.get("/archive/visits/new/")

        assert resp.status_code == 200
        assert "core/archive/visit_create.html" in [t.name for t in resp.templates]

    def test_비로그인_사용자가_방문_기록_작성_페이지에_접근하면_로그인_페이지로_리다이렉트된다(
        self,
    ):
        resp = Client().get("/archive/visits/new/")

        assert resp.status_code == 302
        assert "/accounts/login" in resp.url

    def test_방문_기록_작성_페이지는_본인이_참석_예정으로_등록한_행사만_선택_목록에_표시한다(
        self, make_user, make_event, make_status
    ):
        user = make_user()
        planned = make_event(title="Planned")
        make_event(title="Other published")  # 게시됐지만 예정 상태는 아니다
        make_status(user, event=planned, status=UserEventStatus.Status.PLANNED)

        client = Client()
        client.force_login(user)
        resp = client.get("/archive/visits/new/")

        assert list(resp.context["selectable_events"]) == [planned]

    def test_방문_기록_작성_페이지는_본인의_장소_항목만_선택_목록에_표시하고_굿즈는_제외한다(
        self, make_user, make_entry
    ):
        user = make_user()
        other = make_user(username="other")
        mine = make_entry(user, kind="place", title="내 장소")
        make_entry(other, kind="place", title="남의 카페")
        # 굿즈는 더 이상 유효한 방문 대상이 아니다(컬렉션 도메인 계획 §3-3) — 과거에
        # 만들어진 기존 행이라도 선택 목록에 노출되면 안 된다.
        make_entry(user, kind="goods", title="내 굿즈")

        client = Client()
        client.force_login(user)
        resp = client.get("/archive/visits/new/")

        entries = list(resp.context["selectable_personal_entries"])
        assert entries == [mine]


@pytest.mark.django_db
class TestArchiveVisitCreatePreselect:
    """?subject=event:<id> / personal:<id> 로 접근하면 작성 폼의 대상이 하나로 고정된다.

    방문 완료 행사는 예정 목록에는 없지만, "기록" 버튼으로 바로 저장 가능한 상태로
    페이지를 열 수 있게 한다.
    """

    def test_게시된_행사를_subject로_지정해_접근하면_해당_행사로_대상이_고정된다(
        self, user_client, make_event
    ):
        _, client = user_client()
        event = make_event(title="방문 완료한 행사")

        resp = client.get(f"/archive/visits/new/?subject=event:{event.id}")

        assert resp.context["preselect"] == {
            "value": f"event:{event.id}",
            "label": "방문 완료한 행사",
            "is_official": True,
        }
        assert b'name="subject"' in resp.content
        assert f"event:{event.id}".encode() in resp.content

    def test_본인이_방문_완료로_표시한_비공개_행사를_subject로_지정해_접근하면_해당_행사로_대상이_고정된다(
        self, user_client, make_draft_event, make_status
    ):
        user, client = user_client()
        draft = make_draft_event(title="비공개 방문 행사")
        make_status(user, event=draft, status="visited")

        resp = client.get(f"/archive/visits/new/?subject=event:{draft.id}")

        assert resp.status_code == 200
        assert resp.context["preselect"] == {
            "value": f"event:{draft.id}",
            "label": "비공개 방문 행사",
            "is_official": True,
        }

    def test_비공개_행사_제목에_HTML이_있어도_잠긴_대상_표시에서_이스케이프된다(
        self, user_client, make_draft_event, make_status
    ):
        user, client = user_client()
        draft = make_draft_event(title="<b>x</b>")
        make_status(user, event=draft, status="visited")

        resp = client.get(f"/archive/visits/new/?subject=event:{draft.id}")

        assert b"&lt;b&gt;x&lt;/b&gt;" in resp.content
        assert b"<b>x</b>" not in resp.content

    def test_본인의_장소_항목을_subject로_지정해_접근하면_해당_항목으로_대상이_고정된다(
        self, user_client, make_entry
    ):
        user, client = user_client()
        entry = make_entry(user, kind="place", title="숨은 카페")

        resp = client.get(f"/archive/visits/new/?subject=personal:{entry.id}")

        assert resp.context["preselect"] == {
            "value": f"personal:{entry.id}",
            "label": "숨은 카페",
            "is_official": False,
        }

    def test_굿즈_항목을_subject로_지정해_접근하면_사전_선택이_무시된다(
        self, user_client, make_entry
    ):
        # 굿즈는 더 이상 유효한 방문 대상이 아니다(컬렉션 도메인 계획 §3-3) — 조작되거나
        # 과거에 만들어진 ?subject=personal:<굿즈id> 로도 폼을 고정시키면 안 된다.
        user, client = user_client()
        entry = make_entry(user, kind="goods", title="굿즈")

        resp = client.get(f"/archive/visits/new/?subject=personal:{entry.id}")

        assert resp.context["preselect"] is None

    def test_방문_완료_표시가_없는_비공개_행사를_subject로_지정해_접근하면_사전_선택이_무시된다(
        self, user_client, make_draft_event
    ):
        _, client = user_client()
        draft = make_draft_event(title="비공개 행사")

        resp = client.get(f"/archive/visits/new/?subject=event:{draft.id}")

        assert resp.context["preselect"] is None

    @pytest.mark.parametrize(
        ("own_status", "other_status", "is_existing"),
        [
            pytest.param("planned", None, True, id="본인_예정_비공개"),
            pytest.param(None, "visited", True, id="타인_방문_완료만_비공개"),
            pytest.param(None, None, False, id="존재하지_않는_id"),
        ],
    )
    def test_방문_완료_표시가_없거나_없는_행사를_subject로_지정해_접근하면_사전_선택이_무시되고_대상_필드에_그_행사가_나오지_않는다(
        self,
        user_client,
        make_user,
        make_draft_event,
        make_status,
        own_status,
        other_status,
        is_existing,
    ):
        user, client = user_client()
        hidden_title = "숨겨야 하는 비공개 제목"
        event_id = 900_101 if is_existing else 987654321
        if is_existing:
            draft = make_draft_event(id=event_id, title=hidden_title)
            if own_status is not None:
                make_status(user, event=draft, status=own_status)
            if other_status is not None:
                make_status(make_user(username="stranger"), event=draft, status=other_status)

        resp = client.get(f"/archive/visits/new/?subject=event:{event_id}")

        assert resp.status_code == 200
        assert resp.context["preselect"] is None
        # 언어 전환 폼이 현재 주소를 그대로 싣기 때문에 본문 전체가 아니라 대상 필드만 본다.
        assert f'value="event:{event_id}"'.encode() not in resp.content
        assert hidden_title.encode() not in resp.content

    def test_타인의_개인_항목을_subject로_지정해_접근하면_사전_선택이_무시된다(
        self, user_client, make_user, make_entry
    ):
        _, client = user_client()
        other = make_user(username="stranger")
        entry = make_entry(other, kind="goods", title="남의 굿즈")

        resp = client.get(f"/archive/visits/new/?subject=personal:{entry.id}")

        assert resp.context["preselect"] is None

    def test_잘못된_형식의_subject_값으로_접근해도_오류_없이_사전_선택이_무시된다(
        self, user_client
    ):
        _, client = user_client()

        # 단순 isdigit() 검사는 통과하지만 int()/ORM에서 예외를 일으킬 수 있는 값들을
        # 포함한다: 비ASCII "숫자"와 범위를 벗어난 id.
        for raw in (
            "garbage",
            "event:",
            "event:abc",
            "weird:1",
            "event:²",  # 위첨자 2 — isdigit()는 True지만 int()는 예외 발생
            "event:" + "9" * 30,  # DB 정수 범위를 벗어남
        ):
            resp = client.get(f"/archive/visits/new/?subject={raw}")
            assert resp.status_code == 200
            assert resp.context["preselect"] is None

    def test_subject_파라미터_없이_접근하면_선택_목록이_그대로_유지된다(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/visits/new/")

        assert resp.context["preselect"] is None
        assert "selectable_events" in resp.context
