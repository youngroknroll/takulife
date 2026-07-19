"""core.promotion.promote_personal_entry — orchestration tests, no HTTP.

Boundary-aware: archive must not import drafts, so the orchestration lives in a
neutral layer (core.promotion). A promotion seeds a PENDING EventDraft from the
user's private item + a required official URL; the item is then marked submitted.
The item stays private until an admin approves the draft into a published Event.
"""
import logging

import pytest

from archive.models import PersonalEntry
from drafts.models import EventDraft
from drafts.services import approve_draft
from core.promotion import (
    PromotionAlreadySubmittedError,
    PromotionDuplicateError,
    PromotionKindNotAllowedError,
    PromotionNotFoundError,
    PromotionUnsafeUrlError,
    promote_personal_entry,
)
from events.models import Event


@pytest.mark.django_db
@pytest.mark.domain
def test_비공식_항목을_공식_URL과_함께_승격하면_드래프트가_생성되고_항목이_제출됨_상태가_된다(make_user, make_entry):
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
@pytest.mark.domain
def test_다른_사용자의_항목을_승격하려_하면_PromotionNotFoundError가_발생한다(make_user, make_entry):
    owner = make_user(username="promo-owner")
    other = make_user(username="promo-other")
    entry = make_entry(owner, kind="place", title="X")

    with pytest.raises(PromotionNotFoundError):
        promote_personal_entry(
            user=other, personal_entry_id=entry.id, official_url="https://x.example.com/x"
        )


@pytest.mark.django_db
@pytest.mark.domain
def test_굿즈_항목을_승격하려_하면_PromotionKindNotAllowedError가_발생하고_상태가_변하지_않는다(make_user, make_entry):
    """GOODS entries are no longer promotable (collection domain plan §3-3) —
    only place entries can be seeded into the official review pipeline."""
    user = make_user(username="promo-goods")
    entry = make_entry(user, kind="goods", title="굿즈")

    with pytest.raises(PromotionKindNotAllowedError):
        promote_personal_entry(
            user=user, personal_entry_id=entry.id, official_url="https://goods.example.com/x"
        )

    entry.refresh_from_db()
    assert entry.promotion_status == PersonalEntry.PromotionStatus.NONE
    assert not EventDraft.objects.filter(source_url="https://goods.example.com/x").exists()


@pytest.mark.django_db
@pytest.mark.domain
def test_이미_제출된_항목을_다시_승격하려_하면_PromotionAlreadySubmittedError가_발생한다(make_user, make_entry):
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
@pytest.mark.domain
def test_ftp_스킴의_공식_URL로_승격하려_하면_PromotionUnsafeUrlError가_발생한다(make_user, make_entry):
    user = make_user(username="promo-unsafe-scheme")
    entry = make_entry(user, kind="place", title="F")

    with pytest.raises(PromotionUnsafeUrlError):
        promote_personal_entry(
            user=user, personal_entry_id=entry.id, official_url="ftp://official.example.com/x"
        )


@pytest.mark.django_db
@pytest.mark.domain
def test_localhost_공식_URL로_승격하려_하면_PromotionUnsafeUrlError가_발생한다(make_user, make_entry):
    user = make_user(username="promo-unsafe-localhost")
    entry = make_entry(user, kind="place", title="G")

    with pytest.raises(PromotionUnsafeUrlError):
        promote_personal_entry(
            user=user, personal_entry_id=entry.id, official_url="http://localhost/x"
        )


@pytest.mark.django_db
@pytest.mark.domain
def test_승격에서_안전하지_않은_url이_거부되어도_경고_로그가_기록되지_않는다(make_user, make_entry, caplog):
    caplog.set_level(logging.WARNING)
    user = make_user(username="promo-unsafe-no-log")
    entry = make_entry(user, kind="place", title="I")

    with pytest.raises(PromotionUnsafeUrlError):
        promote_personal_entry(
            user=user, personal_entry_id=entry.id, official_url="http://localhost/x"
        )

    warnings = [
        record
        for record in caplog.records
        if record.levelno >= logging.WARNING and record.name.startswith("core")
    ]
    assert warnings == []


@pytest.mark.django_db
@pytest.mark.domain
def test_사설_IP_리터럴_공식_URL로_승격하려_하면_PromotionUnsafeUrlError가_발생한다(make_user, make_entry):
    user = make_user(username="promo-unsafe-private-ip")
    entry = make_entry(user, kind="place", title="H")

    with pytest.raises(PromotionUnsafeUrlError):
        promote_personal_entry(
            user=user, personal_entry_id=entry.id, official_url="http://192.168.0.1/x"
        )


@pytest.mark.django_db
@pytest.mark.domain
def test_이미_사용중인_공식_URL로_승격하려_하면_PromotionDuplicateError가_발생한다(make_user, make_entry):
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
@pytest.mark.contract
def test_중복_URL_승격_실패는_트랜잭션이_롤백되어_항목이_제출됨으로_바뀌지_않는다(make_user, make_entry):
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
@pytest.mark.domain
def test_승격된_항목은_관리자가_드래프트를_승인하기_전까지_비공개로_유지되다가_승인_후_공개_행사로_전환된다(make_user, make_entry):
    user = make_user(username="promo-private")
    entry = make_entry(user, kind="place", title="숨은 카페")
    result = promote_personal_entry(
        user=user, personal_entry_id=entry.id, official_url="https://priv.example.com/c"
    )

    # Not published yet — absent from the public catalog.
    assert not Event.objects.published().filter(title="숨은 카페").exists()

    # Admin approves the seeded draft → it becomes a published Event.
    approve_draft(draft_id=result.draft_id, actor=user)
    assert Event.objects.published().filter(official_url="https://priv.example.com/c").exists()
