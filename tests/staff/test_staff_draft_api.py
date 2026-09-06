import pytest
from django.db import IntegrityError
from django.test import override_settings
from django.urls import resolve, reverse

import staff.views.draft_api as draft_views
from drafts.models import EventDraft
from drafts.services import (
    DraftCreationEmptyExtractionError,
    DraftCreationResponseTooLargeError,
    DraftCreationUnsupportedContentError,
)
from events.models import Event
from staff.models import StaffActionLog

pytestmark = pytest.mark.web


def _raise(exc):
    def _fn(*args, **kwargs):
        raise exc

    return _fn


def event_drafts_url():
    return reverse("event-drafts")


def event_draft_detail_url(draft_id):
    return reverse("event-draft-detail", kwargs={"pk": draft_id})


@pytest.mark.django_db
@override_settings(DRAFT_DISCOVERY_ENABLED=True)
def test_관리자가_url로_이벤트_드래프트를_생성하면_추출된_필드와_함께_저장된다(admin_client, monkeypatch):
    def fake_fetch(url):
        return "<html><title>Sample Event</title><meta name='description' content='Short summary'></html>"

    def fake_extract(html):
        return {
            "raw_title": "Sample Event",
            "raw_text": "Short summary",
            "extracted_title": "Sample Event",
            "extracted_summary": "Short summary",
            "extracted_category": "popup_store",
            "extracted_region": "seoul",
        }

    monkeypatch.setattr("drafts.services.fetch_html", fake_fetch)
    monkeypatch.setattr("drafts.services.extract_event_fields", fake_extract)
    response = admin_client.post(event_drafts_url(), {"source_url": "https://example.com/event"})

    assert response.status_code == 201
    created = EventDraft.objects.get(source_url="https://example.com/event")
    assert created.extracted_title == "Sample Event"
    assert created.extracted_category == "popup_store"
    assert created.review_status == EventDraft.ReviewStatus.PENDING


@pytest.mark.django_db
@override_settings(DRAFT_DISCOVERY_ENABLED=True)
def test_관리자가_안전하지_않은_url로_생성을_요청하면_400과_함께_거부된다_로그도_남지_않는다(admin_client):
    response = admin_client.post(event_drafts_url(), {"source_url": "http://127.0.0.1/event"})

    assert response.status_code == 400
    assert response.json() == {"detail": "Unsafe URL is not allowed."}
    assert not EventDraft.objects.filter(source_url="http://127.0.0.1/event").exists()
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
@override_settings(DRAFT_DISCOVERY_ENABLED=True)
def test_url_가져오기가_실패하면_503으로_응답하고_드래프트를_생성하지_않는다(admin_client, monkeypatch):
    monkeypatch.setattr("drafts.services.fetch_html", lambda url: (_ for _ in ()).throw(RuntimeError("timeout")))
    admin_client.raise_request_exception = False

    response = admin_client.post(event_drafts_url(), {"source_url": "https://example.com/event"})

    assert response.status_code == 503
    assert response.json() == {"detail": "Failed to fetch source URL."}
    assert not EventDraft.objects.filter(source_url="https://example.com/event").exists()


@pytest.mark.django_db
def test_관리자는_이벤트_드래프트_상세를_조회할_수_있다(admin_client, make_draft):
    draft = make_draft("https://example.com/event")

    response = admin_client.get(event_draft_detail_url(draft.id))

    assert response.status_code == 200
    assert response.json()["id"] == draft.id


@pytest.mark.django_db
def test_이벤트_드래프트_상세_응답은_extraction_method와_confidence를_포함한다(admin_client, make_draft):
    draft = make_draft("https://example.com/event", extraction_method=EventDraft.ExtractionMethod.LLM, confidence=0.87)

    response = admin_client.get(event_draft_detail_url(draft.id))

    response_data = response.json()
    assert response_data["extraction_method"] == "llm"
    assert response_data["confidence"] == pytest.approx(0.87)


@pytest.mark.django_db
def test_관리자는_검토_대기중인_드래프트의_추출_필드를_수정할_수_있다(admin_client, make_draft):
    draft = make_draft("https://example.com/event")

    response = admin_client.patch(
        event_draft_detail_url(draft.id),
        {"extracted_title": "Updated title", "extracted_region": "seoul"},
        content_type="application/json",
    )

    assert response.status_code == 200
    draft.refresh_from_db()
    assert draft.extracted_title == "Updated title"
    assert draft.extracted_region == "seoul"


@pytest.mark.django_db
def test_승인된_드래프트는_수정할_수_없다_로그도_남지_않는다(admin_client, make_draft):
    draft = make_draft("https://example.com/event", extracted_title="Original title", review_status=EventDraft.ReviewStatus.APPROVED)

    response = admin_client.patch(
        event_draft_detail_url(draft.id),
        {"extracted_title": "Changed title"},
        content_type="application/json",
    )

    assert response.status_code == 400
    draft.refresh_from_db()
    assert draft.extracted_title == "Original title"
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
def test_거절된_드래프트는_수정할_수_없다_로그도_남지_않는다(admin_client, make_draft):
    draft = make_draft("https://example.com/event", extracted_title="Original title", review_status=EventDraft.ReviewStatus.REJECTED)

    response = admin_client.patch(
        event_draft_detail_url(draft.id),
        {"extracted_title": "Changed title"},
        content_type="application/json",
    )

    assert response.status_code == 400
    draft.refresh_from_db()
    assert draft.extracted_title == "Original title"
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
def test_source_url과_원본_필드는_수정할_수_없다(admin_client, make_draft):
    draft = make_draft("https://example.com/event", raw_title="Original raw title", raw_text="Original raw text")

    response = admin_client.patch(
        event_draft_detail_url(draft.id),
        {
            "source_url": "https://example.com/changed",
            "raw_title": "Changed raw title",
            "raw_text": "Changed raw text",
        },
        content_type="application/json",
    )

    assert response.status_code == 400
    response_data = response.json()
    assert "source_url" in response_data
    assert "raw_title" in response_data
    assert "raw_text" in response_data
    draft.refresh_from_db()
    assert draft.source_url == "https://example.com/event"
    assert draft.raw_title == "Original raw title"
    assert draft.raw_text == "Original raw text"


@pytest.mark.django_db
def test_review_status는_patch로_직접_변경할_수_없다(admin_client, make_draft):
    draft = make_draft("https://example.com/event", extracted_title="Original title")

    response = admin_client.patch(
        event_draft_detail_url(draft.id),
        {
            "review_status": EventDraft.ReviewStatus.APPROVED,
            "extracted_title": "Changed title",
        },
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json() == {"review_status": ["This field cannot be updated."]}
    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.PENDING
    assert draft.extracted_title == "Original title"
    assert not Event.objects.filter(official_url="https://example.com/event").exists()


@pytest.mark.django_db
def test_extraction_method와_confidence는_patch로_변경할_수_없다(admin_client, make_draft):
    draft = make_draft("https://example.com/event")

    response = admin_client.patch(
        event_draft_detail_url(draft.id),
        {"extraction_method": "llm", "confidence": 0.9},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json() == {
        "extraction_method": ["This field cannot be updated."],
        "confidence": ["This field cannot be updated."],
    }
    draft.refresh_from_db()
    assert draft.extraction_method == EventDraft.ExtractionMethod.HEURISTIC
    assert draft.confidence is None


@pytest.mark.django_db
def test_이벤트_드래프트에_put_요청을_보내면_405가_된다(admin_client, make_draft):
    draft = make_draft("https://example.com/event")

    response = admin_client.put(
        event_draft_detail_url(draft.id),
        {"extracted_title": "Changed title"},
        content_type="application/json",
    )

    assert response.status_code == 405


@pytest.mark.django_db
def test_일반_사용자는_이벤트_드래프트_검토_기능에_접근할_수_없다(client, make_user, make_draft):
    user = make_user()
    draft = make_draft("https://example.com/event")
    client.force_login(user)

    list_response = client.get(event_drafts_url())
    create_response = client.post(event_drafts_url(), {"source_url": "https://example.com/other"})
    detail_response = client.get(event_draft_detail_url(draft.id))
    patch_response = client.patch(
        event_draft_detail_url(draft.id),
        {"extracted_title": "Changed title"},
        content_type="application/json",
    )

    assert list_response.status_code == 403
    assert create_response.status_code == 403
    assert detail_response.status_code == 403
    assert patch_response.status_code == 403


@pytest.mark.django_db
@override_settings(DRAFT_DISCOVERY_ENABLED=True)
def test_이미_존재하는_source_url로_생성을_요청하면_거부된다_로그도_남지_않는다(admin_client, make_draft):
    make_draft("https://example.com/event")

    response = admin_client.post(event_drafts_url(), {"source_url": "https://example.com/event"})

    assert response.status_code == 400
    assert "source_url" in response.json()
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
@override_settings(DRAFT_DISCOVERY_ENABLED=True)
def test_생성_시점의_동시성_경쟁으로_인한_중복도_source_url_필드_오류로_응답한다_로그도_남지_않는다(admin_client, monkeypatch):
    monkeypatch.setattr("drafts.services.fetch_html", lambda url: "<title>Event</title>")
    monkeypatch.setattr(
        "drafts.services.extract_event_fields",
        lambda html: {"raw_title": "Event", "raw_text": "Summary"},
    )

    def raise_integrity_error(**kwargs):
        raise IntegrityError("duplicate")

    monkeypatch.setattr("drafts.services.EventDraft.objects.create", raise_integrity_error)

    response = admin_client.post(event_drafts_url(), {"source_url": "https://example.com/event"})

    assert response.status_code == 400
    assert response.json() == {"source_url": ["Event draft with this source URL already exists."]}
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
@override_settings(DRAFT_DISCOVERY_ENABLED=True)
def test_http가_아닌_스킴의_url로_생성을_요청하면_거부된다_로그도_남지_않는다(admin_client):
    response = admin_client.post(event_drafts_url(), {"source_url": "ftp://example.com/event"})

    assert response.status_code == 400
    assert "source_url" in response.json()
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
def test_수집이_비활성화되어_있으면_관리자의_수동_드래프트_생성도_거부된다_로그도_남지_않는다(admin_client, monkeypatch):
    # settings.DRAFT_DISCOVERY_ENABLED는 기본 False(config/settings.py). 관리자
    # 권한과 무관하게 이 게이트가 fetch 시도 자체를 막아야 한다 — fetch_html이
    # 실제로 불리면 SSRF 방어가 우회될 수 있으므로, 여기서는 fetch_html을
    # 호출되면 즉시 실패하는 대역으로 바꿔 미시도임을 증명한다.
    def _must_not_fetch(url):
        raise AssertionError("DRAFT_DISCOVERY_ENABLED가 False일 때 fetch_html이 호출되면 안 된다")

    monkeypatch.setattr("drafts.services.fetch_html", _must_not_fetch)

    response = admin_client.post(event_drafts_url(), {"source_url": "https://example.com/gated"})

    assert response.status_code == 403
    assert not EventDraft.objects.filter(source_url="https://example.com/gated").exists()
    assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
def test_이벤트_드래프트_구_경로는_더_이상_지원되지_않는다(admin_client):
    response = admin_client.get("/api/admin/event-drafts/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_이벤트_드래프트는_삭제할_수_없다(admin_client, make_draft):
    draft = make_draft("https://example.com/event")

    response = admin_client.delete(event_draft_detail_url(draft.id))

    assert response.status_code == 405
    assert EventDraft.objects.filter(id=draft.id).exists()


def stats_url():
    return reverse("event-draft-stats")


@pytest.mark.django_db
def test_드래프트_통계는_검토_상태별_건수를_정확히_집계한다(admin_client, make_draft):
    make_draft("https://example.com/p1")
    make_draft("https://example.com/p2")
    make_draft("https://example.com/a1", review_status=EventDraft.ReviewStatus.APPROVED)
    make_draft("https://example.com/r1", review_status=EventDraft.ReviewStatus.REJECTED)

    response = admin_client.get(stats_url())

    assert response.status_code == 200
    data = response.json()
    assert data["pending"] == 2
    assert data["approved"] == 1
    assert data["rejected"] == 1


@pytest.mark.django_db
def test_드래프트가_없으면_통계는_모두_0을_반환한다(admin_client):
    response = admin_client.get(stats_url())

    assert response.status_code == 200
    data = response.json()
    assert data == {"pending": 0, "approved": 0, "rejected": 0}


@pytest.mark.django_db
def test_일반_사용자는_드래프트_통계를_조회할_수_없다(client, make_user):
    user = make_user()
    client.force_login(user)

    response = client.get(stats_url())

    assert response.status_code == 403


@pytest.mark.django_db
def test_비로그인_사용자는_드래프트_통계를_조회할_수_없다(client):
    response = client.get(stats_url())

    assert response.status_code == 403


class TestRouteOrdering:
    def test_stats_경로는_통계_뷰로_해석된다(self):
        match = resolve("/api/event-drafts/stats/")
        assert match.url_name == "event-draft-stats"

    def test_숫자_pk_경로는_상세_뷰로_해석된다(self):
        match = resolve("/api/event-drafts/1/")
        assert match.url_name == "event-draft-detail"


@pytest.mark.django_db
class TestAdminCreateEndpointErrorResponses:
    def _post(self, client):
        return client.post(
            "/api/event-drafts/",
            data={"source_url": "https://ok.example.com/"},
            content_type="application/json",
        )

    @override_settings(DRAFT_DISCOVERY_ENABLED=True)
    def test_지원하지_않는_콘텐츠_오류는_400으로_응답한다_로그도_남지_않는다(self, staff_client, monkeypatch):
        monkeypatch.setattr(
            draft_views, "prepare_draft_from_url",
            _raise(DraftCreationUnsupportedContentError()),
        )
        _, client = staff_client(is_superuser=True)
        resp = self._post(client)
        assert resp.status_code == 400
        assert StaffActionLog.objects.count() == 0

    @override_settings(DRAFT_DISCOVERY_ENABLED=True)
    def test_응답_크기_초과_오류는_400으로_응답한다_로그도_남지_않는다(self, staff_client, monkeypatch):
        monkeypatch.setattr(
            draft_views, "prepare_draft_from_url",
            _raise(DraftCreationResponseTooLargeError()),
        )
        _, client = staff_client(is_superuser=True)
        resp = self._post(client)
        assert resp.status_code == 400
        assert StaffActionLog.objects.count() == 0

    @override_settings(DRAFT_DISCOVERY_ENABLED=True)
    def test_추출_결과_없음_오류는_400으로_응답한다_로그도_남지_않는다(self, staff_client, monkeypatch):
        monkeypatch.setattr(
            draft_views, "prepare_draft_from_url",
            _raise(DraftCreationEmptyExtractionError()),
        )
        _, client = staff_client(is_superuser=True)
        resp = self._post(client)
        assert resp.status_code == 400
        assert StaffActionLog.objects.count() == 0


@pytest.mark.django_db
class TestDraftUpdateApiVocabError:
    """PATCH /api/event-drafts/<id>/ 는 DraftStateError만 잡고 있었다.
    어휘(core.vocab) 위반이 여기로 올라오면 500이 되므로 400으로 번역해야 한다.
    서비스 계층 가드 자체는 tests/drafts/test_draft_vocab_guard.py가 검증한다."""

    def test_어휘_밖_카테고리로_PATCH하면_500이_아니라_400을_응답한다_로그도_남지_않는다(
        self, admin_client, make_draft
    ):
        draft = make_draft(extracted_category="popup_store")

        resp = admin_client.patch(
            f"/api/event-drafts/{draft.id}/",
            {"extracted_category": "카페/팝업"},
            content_type="application/json",
        )

        assert resp.status_code == 400
        draft.refresh_from_db()
        assert draft.extracted_category == "popup_store"
        assert StaffActionLog.objects.count() == 0

    def test_어휘_밖_지역으로_PATCH하면_400을_응답한다_로그도_남지_않는다(self, admin_client, make_draft):
        draft = make_draft(extracted_region="seoul")

        resp = admin_client.patch(
            f"/api/event-drafts/{draft.id}/",
            {"extracted_region": "서울특별시"},
            content_type="application/json",
        )

        assert resp.status_code == 400
        draft.refresh_from_db()
        assert draft.extracted_region == "seoul"
        assert StaffActionLog.objects.count() == 0