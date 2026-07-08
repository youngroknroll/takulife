"""core.promotion.promote_personal_entry — orchestration tests, no HTTP.

Boundary-aware: archive must not import drafts, so the orchestration lives in a
neutral layer (core.promotion). A promotion seeds a PENDING EventDraft from the
user's private item + a required official URL; the item is then marked submitted.
The item stays private until an admin approves the draft into a published Event.
"""
import pytest

from archive.models import PersonalEntry
from drafts.models import EventDraft
from drafts.services import approve_draft
from core.promotion import (
    PromotionAlreadySubmittedError,
    PromotionDuplicateError,
    PromotionNotFoundError,
    PromotionUnsafeUrlError,
    promote_personal_entry,
)
from events.models import Event


@pytest.mark.django_db
def test_promote_creates_draft_and_marks_entry_submitted(make_user, make_entry):
    user = make_user(username="promo")
    entry = make_entry(user, kind="place", title="비공식 카페", location_name="연남동", memo="좋음")

    result = promote_personal_entry(
        user=user, personal_entry_id=entry.id, official_url="https://off.example.com/cafe"
    )

    draft = EventDraft.objects.get(pk=result.draft_id)
    assert draft.extracted_title == "비공식 카페"
    assert draft.source_url == "https://off.example.com/cafe"
    entry.refresh_from_db()
    assert entry.promotion_status == PersonalEntry.PromotionStatus.SUBMITTED


@pytest.mark.django_db
def test_promote_other_users_entry_not_found(make_user, make_entry):
    owner = make_user(username="promo-owner")
    other = make_user(username="promo-other")
    entry = make_entry(owner, kind="goods", title="X")

    with pytest.raises(PromotionNotFoundError):
        promote_personal_entry(
            user=other, personal_entry_id=entry.id, official_url="https://x.example.com/x"
        )


@pytest.mark.django_db
def test_promote_already_submitted_raises(make_user, make_entry):
    user = make_user(username="promo-twice")
    entry = make_entry(user, kind="place", title="C")
    promote_personal_entry(
        user=user, personal_entry_id=entry.id, official_url="https://c.example.com/c1"
    )

    with pytest.raises(PromotionAlreadySubmittedError):
        promote_personal_entry(
            user=user, personal_entry_id=entry.id, official_url="https://c.example.com/c2"
        )


@pytest.mark.django_db
def test_promote_rejects_unsafe_official_url_scheme(make_user, make_entry):
    user = make_user(username="promo-unsafe-scheme")
    entry = make_entry(user, kind="place", title="F")

    with pytest.raises(PromotionUnsafeUrlError):
        promote_personal_entry(
            user=user, personal_entry_id=entry.id, official_url="ftp://official.example.com/x"
        )


@pytest.mark.django_db
def test_promote_rejects_localhost_official_url(make_user, make_entry):
    user = make_user(username="promo-unsafe-localhost")
    entry = make_entry(user, kind="place", title="G")

    with pytest.raises(PromotionUnsafeUrlError):
        promote_personal_entry(
            user=user, personal_entry_id=entry.id, official_url="http://localhost/x"
        )


@pytest.mark.django_db
def test_promote_rejects_private_ip_literal_official_url(make_user, make_entry):
    user = make_user(username="promo-unsafe-private-ip")
    entry = make_entry(user, kind="place", title="H")

    with pytest.raises(PromotionUnsafeUrlError):
        promote_personal_entry(
            user=user, personal_entry_id=entry.id, official_url="http://192.168.0.1/x"
        )


@pytest.mark.django_db
def test_promote_duplicate_official_url_raises(make_user, make_entry):
    user = make_user(username="promo-dup")
    existing = make_entry(user, kind="place", title="D1")
    promote_personal_entry(
        user=user, personal_entry_id=existing.id, official_url="https://d.example.com/d"
    )
    entry = make_entry(user, kind="place", title="D2")

    with pytest.raises(PromotionDuplicateError):
        promote_personal_entry(
            user=user, personal_entry_id=entry.id, official_url="https://d.example.com/d"
        )


@pytest.mark.django_db
def test_failed_promotion_does_not_mark_submitted(make_user, make_entry):
    """A duplicate-url failure must roll back; the entry stays promotable."""
    user = make_user(username="promo-rollback")
    first = make_entry(user, kind="place", title="E1")
    promote_personal_entry(
        user=user, personal_entry_id=first.id, official_url="https://e.example.com/e"
    )
    entry = make_entry(user, kind="place", title="E2")

    with pytest.raises(PromotionDuplicateError):
        promote_personal_entry(
            user=user, personal_entry_id=entry.id, official_url="https://e.example.com/e"
        )

    entry.refresh_from_db()
    assert entry.promotion_status == PersonalEntry.PromotionStatus.NONE


# ---------------------------------------------------------------------------
# End-to-end: promote → admin approve → published Event (privacy preserved)
# (moved from tests/archive/test_promotion_api.py — PR-9 carried this test into
# the API file, but it never calls the HTTP endpoint; both promote_personal_entry
# and approve_draft are called directly, so it belongs here.)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_promoted_entry_stays_private_until_approved(make_user, make_entry):
    user = make_user(username="promo-private")
    entry = make_entry(user, kind="place", title="숨은 카페")
    result = promote_personal_entry(
        user=user, personal_entry_id=entry.id, official_url="https://priv.example.com/c"
    )

    # Not published yet — absent from the public catalog.
    assert not Event.objects.published().filter(title="숨은 카페").exists()

    # Admin approves the seeded draft → it becomes a published Event.
    approve_draft(result.draft_id, actor=user)
    assert Event.objects.published().filter(official_url="https://priv.example.com/c").exists()
