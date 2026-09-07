import datetime

import pytest
import httpx
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from drafts.fetching import MAX_RESPONSE_BYTES, ResponseTooLargeError, fetch_html
from drafts.models import EventDraft
from drafts.services import (
    DraftCreationEmptyExtractionError,
    DraftCreationDuplicateError,
    DraftCreationUnsafeUrlError,
    DraftImmutableFieldError,
    DraftPublicationError,
    DraftPublicationTitleError,
    DraftStateError,
    approve_draft,
    create_draft_from_fields,
    create_draft_from_url,
    reject_draft,
    update_draft,
)
from drafts.url_safety import validate_fetch_url
from events.models import Event

pytestmark = pytest.mark.domain


@pytest.mark.django_db
def test_드래프트를_승인하면_게시된_행사가_생성되고_드래프트가_승인_상태가_된다(make_user, make_draft):
    actor = make_user()
    draft = make_draft("https://example.com/event", source_name="Official", extracted_title="Popup event", extracted_category="popup_store", extracted_region="seoul")

    before = timezone.now()
    result = approve_draft(draft_id=draft.id, actor=actor)

    draft.refresh_from_db()
    event = Event.objects.get(id=result.event_id)
    assert result.draft.id == draft.id
    assert draft.review_status == EventDraft.ReviewStatus.APPROVED
    assert event.publish_status == Event.PublishStatus.PUBLISHED
    assert event.official_url == "https://example.com/event"
    assert event.title == "Popup event"
    assert event.category == "popup_store"
    assert draft.reviewed_by_id == actor.id
    assert draft.approved_at is not None
    assert draft.approved_at >= before


@pytest.mark.django_db
def test_드래프트를_거절하면_행사_생성_없이_거절_상태가_된다(make_user, make_draft):
    actor = make_user()
    draft = make_draft("https://example.com/rejected-event", extracted_title="Rejected event")

    before = timezone.now()
    result = reject_draft(draft_id=draft.id, actor=actor)

    draft.refresh_from_db()
    assert result.id == draft.id
    assert draft.review_status == EventDraft.ReviewStatus.REJECTED
    assert not Event.objects.filter(official_url="https://example.com/rejected-event").exists()
    assert draft.reviewed_by_id == actor.id
    assert draft.rejected_at is not None
    assert draft.rejected_at >= before
    assert draft.rejection_reason == ""


@pytest.mark.django_db
def test_드래프트_거절_시_거절_사유를_기록한다(make_user, make_draft):
    actor = make_user()
    draft = make_draft("https://example.com/rejected-with-reason")

    reject_draft(draft_id=draft.id, actor=actor, rejection_reason="duplicate listing")

    draft.refresh_from_db()
    assert draft.rejection_reason == "duplicate listing"


@pytest.mark.django_db
def test_드래프트_승인_후_게시까지_승인자_귀속_정보가_유지된다(make_user, make_draft):
    actor = make_user()
    draft = make_draft("https://example.com/attributed-event", extracted_title="Attributed event")

    result = approve_draft(draft_id=draft.id, actor=actor)

    draft.refresh_from_db()
    assert Event.objects.filter(id=result.event_id, publish_status=Event.PublishStatus.PUBLISHED).exists()
    assert draft.reviewed_by_id == actor.id
    assert draft.approved_at is not None


@pytest.mark.django_db
def test_시작일이_종료일보다_늦으면_승인이_거부되고_대기_상태를_유지한다(make_user, make_draft):
    actor = make_user()
    draft = make_draft("https://example.com/inverted-period", extracted_title="Inverted period event", extracted_start_date=datetime.date(2026, 8, 10), extracted_end_date=datetime.date(2026, 8, 1))

    with pytest.raises(DraftPublicationError):
        approve_draft(draft_id=draft.id, actor=actor)

    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.PENDING
    assert not Event.objects.filter(official_url="https://example.com/inverted-period").exists()


@pytest.mark.django_db
def test_제목이_비어있으면_승인이_거부되고_대기_상태를_유지한다(make_user, make_draft):
    actor = make_user()
    draft = make_draft("https://example.com/blank-title-draft")

    with pytest.raises(DraftPublicationTitleError):
        approve_draft(draft_id=draft.id, actor=actor)

    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.PENDING
    assert draft.reviewed_by_id is None
    assert draft.approved_at is None
    assert not Event.objects.filter(official_url="https://example.com/blank-title-draft").exists()


@pytest.mark.django_db
def test_제목이_원본_URL과_같으면_승인이_거부되고_대기_상태를_유지한다(make_user, make_draft):
    actor = make_user()
    draft = make_draft("https://example.com/self-titled-draft", extracted_title="https://example.com/self-titled-draft")

    with pytest.raises(DraftPublicationTitleError):
        approve_draft(draft_id=draft.id, actor=actor)

    draft.refresh_from_db()
    assert draft.review_status == EventDraft.ReviewStatus.PENDING
    assert draft.reviewed_by_id is None
    assert draft.approved_at is None
    assert not Event.objects.filter(official_url="https://example.com/self-titled-draft").exists()


@pytest.mark.django_db
def test_대기_상태_드래프트는_필드_수정이_반영된다(make_draft):
    draft = make_draft("https://example.com/event")

    updated = update_draft(draft_id=draft.id, updates={"extracted_title": "Updated title", "extracted_region": "seoul"})

    draft.refresh_from_db()
    assert updated.id == draft.id
    assert draft.extracted_title == "Updated title"
    assert draft.extracted_region == "seoul"


@pytest.mark.django_db
def test_대기_상태가_아닌_드래프트는_수정할_수_없다(make_draft):
    draft = make_draft("https://example.com/event", review_status=EventDraft.ReviewStatus.APPROVED)

    with pytest.raises(DraftStateError):
        update_draft(draft_id=draft.id, updates={"extracted_title": "Updated title"})


@pytest.mark.django_db
def test_URL로_드래프트를_생성하면_페이지를_가져와_필드를_추출한다(monkeypatch):
    monkeypatch.setattr("drafts.services.fetch_html", lambda url: "<html><title>Sample Event</title></html>")
    monkeypatch.setattr(
        "drafts.services.extract_event_fields",
        lambda html: {
            "raw_title": "Sample Event",
            "raw_text": "Sample summary",
            "extracted_title": "Sample Event",
            "extracted_summary": "Sample summary",
            "extracted_category": "popup_store",
            "extracted_region": "seoul",
        },
    )

    draft = create_draft_from_url(source_url="https://example.com/event")

    assert draft.review_status == EventDraft.ReviewStatus.PENDING
    assert draft.raw_title == "Sample Event"
    assert draft.extracted_title == "Sample Event"
    assert draft.extracted_category == "popup_store"


@pytest.mark.django_db
def test_추출_결과가_비어있으면_드래프트_생성이_실패한다(monkeypatch):
    monkeypatch.setattr("drafts.services.fetch_html", lambda url: "<html></html>")
    monkeypatch.setattr("drafts.services.extract_event_fields", lambda html: {"raw_title": "", "raw_text": ""})

    with pytest.raises(DraftCreationEmptyExtractionError):
        create_draft_from_url(source_url="https://example.com/event")


@pytest.mark.django_db
def test_리다이렉트_대상이_비공개_IP면_드래프트_생성이_거부된다(monkeypatch):
    client_class = httpx.Client

    def handler(request):
        return httpx.Response(302, headers={"location": "http://127.0.0.1/private"})

    monkeypatch.setattr(
        "drafts.fetching.httpx.Client",
        lambda **kwargs: client_class(transport=httpx.MockTransport(handler), **kwargs),
    )
    monkeypatch.setattr(
        "drafts.fetching.validate_fetch_url",
        lambda url, **kwargs: validate_fetch_url(url),
    )

    with pytest.raises(DraftCreationUnsafeUrlError):
        create_draft_from_url(source_url="https://example.com/event")


def test_응답_크기가_초과되면_스트림을_끝까지_읽지_않고_즉시_거부한다(monkeypatch):
    chunks_read = 0
    client_class = httpx.Client

    def handler(request):
        class CountingStream(httpx.SyncByteStream):
            def __iter__(self):
                nonlocal chunks_read
                for chunk in (b"a" * MAX_RESPONSE_BYTES, b"bc", b"unread"):
                    chunks_read += 1
                    yield chunk

        return httpx.Response(
            200,
            headers={"content-type": "text/html; charset=utf-8"},
            stream=CountingStream(),
        )

    monkeypatch.setattr(
        "drafts.fetching.httpx.Client",
        lambda **kwargs: client_class(transport=httpx.MockTransport(handler), **kwargs),
    )
    monkeypatch.setattr("drafts.fetching.validate_fetch_url", lambda url, **kwargs: None)

    with pytest.raises(ResponseTooLargeError):
        fetch_html("https://example.com/event")

    assert chunks_read == 2


@pytest.mark.django_db
def test_동시_생성으로_인한_무결성_오류는_중복_드래프트_오류로_변환된다(monkeypatch):
    monkeypatch.setattr("drafts.services.fetch_html", lambda url: "<title>Event</title>")
    monkeypatch.setattr(
        "drafts.services.extract_event_fields",
        lambda html: {"raw_title": "Event", "raw_text": "Summary"},
    )

    def raise_integrity_error(**kwargs):
        raise IntegrityError("duplicate")

    monkeypatch.setattr("drafts.services.EventDraft.objects.create", raise_integrity_error)

    with pytest.raises(DraftCreationDuplicateError):
        create_draft_from_url(source_url="https://example.com/event")


@pytest.mark.django_db
def test_URL_드래프트_생성의_중복_처리는_세이브포인트_안에서_실행된다(monkeypatch):
    """EventDraft.objects.create()는 자신만의 중첩 atomic 블록(세이브포인트)
    안에서 실행돼야 한다. 그래야 web.promotion.promote_personal_entry처럼
    바깥 transaction.atomic() 안에서 호출될 때 여기서 잡은 IntegrityError가
    호출자의 이후 쿼리까지 막지 않는다(Postgres는 세이브포인트 없이는 문장
    오류 시 트랜잭션 전체를 중단시킨다)."""
    monkeypatch.setattr("drafts.services.fetch_html", lambda url: "<title>Event</title>")
    monkeypatch.setattr(
        "drafts.services.extract_event_fields",
        lambda html: {"raw_title": "Event", "raw_text": "Summary"},
    )

    def raise_integrity_error(**kwargs):
        raise IntegrityError("duplicate")

    monkeypatch.setattr("drafts.services.EventDraft.objects.create", raise_integrity_error)

    with transaction.atomic():
        with CaptureQueriesContext(connection) as ctx:
            with pytest.raises(DraftCreationDuplicateError):
                create_draft_from_url(source_url="https://example.com/event")

    assert any("SAVEPOINT" in query["sql"].upper() for query in ctx.captured_queries)


@pytest.mark.django_db
def test_직접_등록_드래프트_생성의_중복_처리도_세이브포인트_안에서_실행된다(monkeypatch):
    """create_draft_from_url과 같은 세이브포인트 보장을, fetch 없이 직접
    생성하는 경로(web.promotion.promote_personal_entry가 자신의 바깥
    transaction.atomic() 안에서 호출)에도 동일하게 적용한다."""

    def raise_integrity_error(**kwargs):
        raise IntegrityError("duplicate")

    monkeypatch.setattr("drafts.services.EventDraft.objects.create", raise_integrity_error)

    with transaction.atomic():
        with CaptureQueriesContext(connection) as ctx:
            with pytest.raises(DraftCreationDuplicateError):
                create_draft_from_fields(source_url="https://example.com/manual", title="A")

    assert any("SAVEPOINT" in query["sql"].upper() for query in ctx.captured_queries)


@pytest.mark.django_db
def test_불변_필드는_서비스_계층에서도_직접_수정이_거부된다(make_draft):
    draft = make_draft("https://example.com/event")

    with pytest.raises(DraftImmutableFieldError):
        update_draft(draft_id=draft.id, updates={"review_status": EventDraft.ReviewStatus.APPROVED})


@pytest.mark.django_db
def test_필드_직접_입력으로_드래프트를_생성하면_대기_상태로_생성된다():
    draft = create_draft_from_fields(
        source_url="https://official.example.com/popup",
        title="공식 팝업",
        category="popup_store",
        location_name="서울 성수",
        summary="메모",
    )

    assert draft.review_status == EventDraft.ReviewStatus.PENDING
    assert draft.source_url == "https://official.example.com/popup"
    assert draft.extracted_title == "공식 팝업"
    assert draft.extracted_location_name == "서울 성수"


@pytest.mark.django_db
def test_같은_URL로_직접_등록을_두_번_하면_중복_오류가_발생한다():
    create_draft_from_fields(source_url="https://dup.example.com/a", title="A")
    with pytest.raises(DraftCreationDuplicateError):
        create_draft_from_fields(source_url="https://dup.example.com/a", title="B")


@pytest.mark.django_db
def test_prepare_draft_from_url은_중복_source_url이어도_예외_없이_페이로드를_돌려준다(monkeypatch):
    """트랙 20 2차(서비스 분할) 전까지는 prepare_draft_from_url이 없어
    ImportError로 Red가 정상이다."""
    monkeypatch.setattr("drafts.services.fetch_html", lambda url: "<html><title>Dup</title></html>")
    monkeypatch.setattr(
        "drafts.services.extract_event_fields",
        lambda html: {"raw_title": "Dup", "raw_text": "Dup summary"},
    )
    create_draft_from_fields(source_url="https://dup.example.com/prepare", title="Existing")

    from drafts.services import prepare_draft_from_url

    payload = prepare_draft_from_url(source_url="https://dup.example.com/prepare")

    assert payload is not None


@pytest.mark.django_db
def test_persist_prepared_draft는_중복_source_url에_DraftCreationDuplicateError를_낸다(monkeypatch):
    """분할 전까지는 persist_prepared_draft가 없어 ImportError로 Red가 정상이다."""
    monkeypatch.setattr("drafts.services.fetch_html", lambda url: "<html><title>Dup</title></html>")
    monkeypatch.setattr(
        "drafts.services.extract_event_fields",
        lambda html: {"raw_title": "Dup", "raw_text": "Dup summary"},
    )
    create_draft_from_fields(source_url="https://dup.example.com/persist", title="Existing")

    from drafts.services import persist_prepared_draft, prepare_draft_from_url

    payload = prepare_draft_from_url(source_url="https://dup.example.com/persist")

    with pytest.raises(DraftCreationDuplicateError):
        persist_prepared_draft(payload=payload)


@pytest.mark.django_db
def test_create_draft_from_url은_분할_전과_같은_드래프트를_만든다(monkeypatch):
    """분할 후 create_draft_from_url(합성 함수)의 겉보기 동작이 그대로인지 지키는
    회귀 핀이라 지금은 Green이 정상이다(기존 test_URL로_드래프트를_생성하면...과 같은
    함수를 다른 각도로 고정)."""
    monkeypatch.setattr("drafts.services.fetch_html", lambda url: "<html><title>Split check</title></html>")
    monkeypatch.setattr(
        "drafts.services.extract_event_fields",
        lambda html: {
            "raw_title": "Split check",
            "raw_text": "Split summary",
            "extracted_title": "Split check",
            "extracted_category": "popup_store",
        },
    )

    draft = create_draft_from_url(source_url="https://example.com/split-check")

    assert draft.source_url == "https://example.com/split-check"
    assert draft.extracted_title == "Split check"
    assert draft.extracted_category == "popup_store"
    assert draft.review_status == EventDraft.ReviewStatus.PENDING
