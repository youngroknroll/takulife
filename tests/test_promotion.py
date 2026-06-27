"""Phase 4: 공식 제보 (promote an unofficial PersonalEntry into the admin draft
review pipeline).

Boundary-aware: archive must not import drafts, so the orchestration lives in a
neutral layer (core.promotion). A promotion seeds a PENDING EventDraft from the
user's private item + a required official URL; the item is then marked submitted.
The item stays private until an admin approves the draft into a published Event.
"""
import pytest

from archive.models import PersonalEntry
from drafts.models import EventDraft
from drafts.services import (
    DraftCreationDuplicateError,
    approve_draft,
    create_draft_from_fields,
)
from core.promotion import (
    PromotionAlreadySubmittedError,
    PromotionDuplicateError,
    PromotionNotFoundError,
    promote_personal_entry,
)
from events.models import Event


# ---------------------------------------------------------------------------
# drafts.create_draft_from_fields — direct (no fetch) draft creation
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_create_draft_from_fields_makes_pending_draft():
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
def test_create_draft_from_fields_duplicate_url_raises():
    create_draft_from_fields(source_url="https://dup.example.com/a", title="A")
    with pytest.raises(DraftCreationDuplicateError):
        create_draft_from_fields(source_url="https://dup.example.com/a", title="B")


# ---------------------------------------------------------------------------
# core.promote_personal_entry — orchestration
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_promote_creates_draft_and_marks_entry_submitted(make_user):
    user = make_user(username="promo")
    entry = PersonalEntry.objects.create(
        user=user, kind="place", title="비공식 카페", location_name="연남동", memo="좋음"
    )

    result = promote_personal_entry(
        user=user, personal_entry_id=entry.id, official_url="https://off.example.com/cafe"
    )

    draft = EventDraft.objects.get(pk=result.draft_id)
    assert draft.extracted_title == "비공식 카페"
    assert draft.source_url == "https://off.example.com/cafe"
    entry.refresh_from_db()
    assert entry.promotion_status == PersonalEntry.PromotionStatus.SUBMITTED


@pytest.mark.django_db
def test_promote_other_users_entry_not_found(make_user):
    owner = make_user(username="promo-owner")
    other = make_user(username="promo-other")
    entry = PersonalEntry.objects.create(user=owner, kind="goods", title="X")

    with pytest.raises(PromotionNotFoundError):
        promote_personal_entry(
            user=other, personal_entry_id=entry.id, official_url="https://x.example.com/x"
        )


@pytest.mark.django_db
def test_promote_already_submitted_raises(make_user):
    user = make_user(username="promo-twice")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="C")
    promote_personal_entry(
        user=user, personal_entry_id=entry.id, official_url="https://c.example.com/c1"
    )

    with pytest.raises(PromotionAlreadySubmittedError):
        promote_personal_entry(
            user=user, personal_entry_id=entry.id, official_url="https://c.example.com/c2"
        )


@pytest.mark.django_db
def test_promote_duplicate_official_url_raises(make_user):
    user = make_user(username="promo-dup")
    existing = PersonalEntry.objects.create(user=user, kind="place", title="D1")
    promote_personal_entry(
        user=user, personal_entry_id=existing.id, official_url="https://d.example.com/d"
    )
    entry = PersonalEntry.objects.create(user=user, kind="place", title="D2")

    with pytest.raises(PromotionDuplicateError):
        promote_personal_entry(
            user=user, personal_entry_id=entry.id, official_url="https://d.example.com/d"
        )


@pytest.mark.django_db
def test_failed_promotion_does_not_mark_submitted(make_user):
    """A duplicate-url failure must roll back; the entry stays promotable."""
    user = make_user(username="promo-rollback")
    first = PersonalEntry.objects.create(user=user, kind="place", title="E1")
    promote_personal_entry(
        user=user, personal_entry_id=first.id, official_url="https://e.example.com/e"
    )
    entry = PersonalEntry.objects.create(user=user, kind="place", title="E2")

    with pytest.raises(PromotionDuplicateError):
        promote_personal_entry(
            user=user, personal_entry_id=entry.id, official_url="https://e.example.com/e"
        )

    entry.refresh_from_db()
    assert entry.promotion_status == PersonalEntry.PromotionStatus.NONE


# ---------------------------------------------------------------------------
# API — POST /api/personal-entries/<id>/promote/
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_api_promote_returns_201_and_marks_submitted(client, make_user):
    user = make_user(username="api-promo")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="비공식")

    client.force_login(user)
    response = client.post(
        f"/api/personal-entries/{entry.id}/promote/",
        {"official_url": "https://api.example.com/p"},
        content_type="application/json",
    )

    assert response.status_code == 201
    entry.refresh_from_db()
    assert entry.promotion_status == PersonalEntry.PromotionStatus.SUBMITTED
    assert EventDraft.objects.filter(source_url="https://api.example.com/p").exists()


@pytest.mark.django_db
def test_api_promote_requires_official_url(client, make_user):
    user = make_user(username="api-promo-nourl")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="비공식")

    client.force_login(user)
    response = client.post(
        f"/api/personal-entries/{entry.id}/promote/",
        {},
        content_type="application/json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_api_promote_other_users_entry_404(client, make_user):
    owner = make_user(username="api-promo-owner")
    other = make_user(username="api-promo-other")
    entry = PersonalEntry.objects.create(user=owner, kind="place", title="비공식")

    client.force_login(other)
    response = client.post(
        f"/api/personal-entries/{entry.id}/promote/",
        {"official_url": "https://api.example.com/p2"},
        content_type="application/json",
    )

    assert response.status_code == 404
    assert not EventDraft.objects.filter(source_url="https://api.example.com/p2").exists()


@pytest.mark.django_db
def test_api_promote_already_submitted_409(client, make_user):
    user = make_user(username="api-promo-twice")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="비공식")
    client.force_login(user)
    client.post(
        f"/api/personal-entries/{entry.id}/promote/",
        {"official_url": "https://api.example.com/q1"},
        content_type="application/json",
    )
    response = client.post(
        f"/api/personal-entries/{entry.id}/promote/",
        {"official_url": "https://api.example.com/q2"},
        content_type="application/json",
    )

    assert response.status_code == 409


@pytest.mark.django_db
def test_api_promote_requires_authentication(client, make_user):
    user = make_user(username="api-promo-anon")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="비공식")

    response = client.post(
        f"/api/personal-entries/{entry.id}/promote/",
        {"official_url": "https://api.example.com/r"},
        content_type="application/json",
    )

    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# End-to-end: promote → admin approve → published Event (privacy preserved)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_promoted_entry_stays_private_until_approved(client, make_user):
    user = make_user(username="promo-private")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="숨은 카페")
    result = promote_personal_entry(
        user=user, personal_entry_id=entry.id, official_url="https://priv.example.com/c"
    )

    # Not published yet — absent from the public catalog.
    assert not Event.objects.published().filter(title="숨은 카페").exists()

    # Admin approves the seeded draft → it becomes a published Event.
    approve_draft(result.draft_id)
    assert Event.objects.published().filter(official_url="https://priv.example.com/c").exists()
