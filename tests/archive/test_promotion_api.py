"""API — POST /api/personal-entries/<id>/promote/

Promotes a private PersonalEntry into the admin draft review pipeline (see
core.promotion.promote_personal_entry for the orchestration itself, tested
directly in tests/archive/test_promotion_service.py). The item stays private
until an admin approves the seeded draft into a published Event.
"""
import pytest

from archive.models import PersonalEntry
from drafts.models import EventDraft


@pytest.mark.django_db
@pytest.mark.web
def test_비공식_항목을_공식_URL과_함께_승격_요청하면_201로_생성되고_제출됨_상태가_된다(client, make_user, make_entry):
    user = make_user(username="api-promo")
    entry = make_entry(user, kind="place", title="비공식")

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
@pytest.mark.web
def test_공식_URL_없이_승격을_요청하면_400으로_거부된다(client, make_user, make_entry):
    user = make_user(username="api-promo-nourl")
    entry = make_entry(user, kind="place", title="비공식")

    client.force_login(user)
    response = client.post(
        f"/api/personal-entries/{entry.id}/promote/",
        {},
        content_type="application/json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
@pytest.mark.web
def test_ftp_스킴의_공식_URL로_승격을_요청하면_400으로_거부된다(client, make_user, make_entry):
    user = make_user(username="api-promo-ftp")
    entry = make_entry(user, kind="place", title="비공식")

    client.force_login(user)
    response = client.post(
        f"/api/personal-entries/{entry.id}/promote/",
        {"official_url": "ftp://official.example.com/p"},
        content_type="application/json",
    )

    assert response.status_code == 400
    entry.refresh_from_db()
    assert entry.promotion_status == PersonalEntry.PromotionStatus.NONE


@pytest.mark.django_db
@pytest.mark.web
def test_localhost_공식_URL로_승격을_요청하면_400으로_거부된다(client, make_user, make_entry):
    user = make_user(username="api-promo-localhost")
    entry = make_entry(user, kind="place", title="비공식")

    client.force_login(user)
    response = client.post(
        f"/api/personal-entries/{entry.id}/promote/",
        {"official_url": "http://localhost/p"},
        content_type="application/json",
    )

    assert response.status_code == 400
    entry.refresh_from_db()
    assert entry.promotion_status == PersonalEntry.PromotionStatus.NONE


@pytest.mark.django_db
@pytest.mark.web
def test_사설_IP_공식_URL로_승격을_요청하면_400으로_거부된다(client, make_user, make_entry):
    user = make_user(username="api-promo-private-ip")
    entry = make_entry(user, kind="place", title="비공식")

    client.force_login(user)
    response = client.post(
        f"/api/personal-entries/{entry.id}/promote/",
        {"official_url": "http://192.168.0.1/p"},
        content_type="application/json",
    )

    assert response.status_code == 400
    entry.refresh_from_db()
    assert entry.promotion_status == PersonalEntry.PromotionStatus.NONE


@pytest.mark.django_db
@pytest.mark.web
def test_굿즈_항목을_승격_요청하면_400으로_거부되고_제출됨으로_바뀌지_않는다(client, make_user, make_entry):
    """A goods entry is not promotable (collection domain plan §3-3) — the
    view must translate PromotionKindNotAllowedError into a controlled 400,
    not let it bubble up as an unhandled 500."""
    user = make_user(username="api-promo-goods")
    entry = make_entry(user, kind="goods", title="굿즈")

    client.force_login(user)
    response = client.post(
        f"/api/personal-entries/{entry.id}/promote/",
        {"official_url": "https://api.example.com/goods"},
        content_type="application/json",
    )

    assert response.status_code == 400
    entry.refresh_from_db()
    assert entry.promotion_status == PersonalEntry.PromotionStatus.NONE
    assert not EventDraft.objects.filter(source_url="https://api.example.com/goods").exists()


@pytest.mark.django_db
@pytest.mark.web
def test_다른_사용자의_항목을_승격_요청하면_404로_숨겨진다(client, make_user, make_entry):
    owner = make_user(username="api-promo-owner")
    other = make_user(username="api-promo-other")
    entry = make_entry(owner, kind="place", title="비공식")

    client.force_login(other)
    response = client.post(
        f"/api/personal-entries/{entry.id}/promote/",
        {"official_url": "https://api.example.com/p2"},
        content_type="application/json",
    )

    assert response.status_code == 404
    assert not EventDraft.objects.filter(source_url="https://api.example.com/p2").exists()


@pytest.mark.django_db
@pytest.mark.web
def test_이미_제출된_항목을_다시_승격_요청하면_409_중복_오류가_된다(client, make_user, make_entry):
    user = make_user(username="api-promo-twice")
    entry = make_entry(user, kind="place", title="비공식")
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
@pytest.mark.web
def test_이미_존재하는_드래프트와_동일한_공식_URL로_승격_요청하면_필드_오류로_거부된다(client, make_user, make_entry, make_draft):
    """(moved from tests/core/test_coverage_supplements.py)"""
    user = make_user()
    entry = make_entry(user, kind="place", title="제보 대상")
    # A draft already owns this official URL → promotion is a duplicate.
    make_draft(source_url="https://dup.example.com/")

    client.force_login(user)
    resp = client.post(
        f"/api/personal-entries/{entry.id}/promote/",
        data={"official_url": "https://dup.example.com/"},
        content_type="application/json",
    )

    assert resp.status_code == 400
    assert "official_url" in resp.json()


@pytest.mark.django_db
@pytest.mark.web
def test_인증되지_않은_요청으로_승격을_시도하면_401_또는_403으로_거부된다(client, make_user, make_entry):
    user = make_user(username="api-promo-anon")
    entry = make_entry(user, kind="place", title="비공식")

    response = client.post(
        f"/api/personal-entries/{entry.id}/promote/",
        {"official_url": "https://api.example.com/r"},
        content_type="application/json",
    )

    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# Rate limiting — the review queue can't be flooded
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.slow
def test_일일_승격_한도를_초과하면_429로_제한된다(client, make_user, make_entry):
    """After the daily promotion cap, further promotes are throttled (429)."""
    user = make_user(username="api-promo-flood")
    client.force_login(user)

    # 20/day budget: 20 distinct promotes succeed, the 21st is throttled.
    for i in range(20):
        entry = make_entry(user, kind="place", title=f"비공식 {i}")
        response = client.post(
            f"/api/personal-entries/{entry.id}/promote/",
            {"official_url": f"https://flood.example.com/{i}"},
            content_type="application/json",
        )
        assert response.status_code == 201, f"promote {i} should succeed"

    extra = make_entry(user, kind="place", title="비공식 초과")
    throttled = client.post(
        f"/api/personal-entries/{extra.id}/promote/",
        {"official_url": "https://flood.example.com/extra"},
        content_type="application/json",
    )

    assert throttled.status_code == 429
    extra.refresh_from_db()
    assert extra.promotion_status == PersonalEntry.PromotionStatus.NONE
