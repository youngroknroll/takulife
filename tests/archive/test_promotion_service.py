"""core.promotion.promote_personal_entry — 오케스트레이션 테스트, HTTP 없음.

경계 인식: archive는 drafts를 임포트하면 안 되므로 오케스트레이션은 중립 계층
(core.promotion)에 둔다. 승격은 사용자의 비공개 항목과 필수 공식 URL로 PENDING
EventDraft를 시드하고, 항목을 제출됨으로 표시한다. 관리자가 드래프트를 승인해
공개 Event로 만들기 전까지 항목은 비공개로 유지된다.
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
    """GOODS 항목은 더 이상 승격할 수 없다(컬렉션 도메인 설계안 §3-3) — place
    항목만 공식 검수 파이프라인으로 시드될 수 있다."""
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
    """중복 URL 실패는 롤백되어야 하며 항목은 계속 승격 가능한 상태로 남는다."""
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
# End-to-end — 승격 → 관리자 승인 → 공개 Event(비공개 유지). HTTP 엔드포인트를
# 거치지 않고 promote_personal_entry와 approve_draft를 직접 호출하므로 API
# 파일이 아닌 여기 속한다.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.domain
def test_승격된_항목은_관리자가_드래프트를_승인하기_전까지_비공개로_유지되다가_승인_후_공개_행사로_전환된다(make_user, make_entry):
    user = make_user(username="promo-private")
    entry = make_entry(user, kind="place", title="숨은 카페")
    result = promote_personal_entry(
        user=user, personal_entry_id=entry.id, official_url="https://priv.example.com/c"
    )

    # 아직 공개되지 않음 — 공개 카탈로그에는 없다
    assert not Event.objects.published().filter(title="숨은 카페").exists()

    # 관리자가 시드된 드래프트를 승인 → 공개 Event가 된다
    approve_draft(draft_id=result.draft_id, actor=user)
    assert Event.objects.published().filter(official_url="https://priv.example.com/c").exists()
