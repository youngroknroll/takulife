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
def test_api_promote_returns_201_and_marks_submitted(client, make_user, make_entry):
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
def test_api_promote_requires_official_url(client, make_user, make_entry):
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
def test_api_promote_rejects_ftp_official_url_400(client, make_user, make_entry):
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
def test_api_promote_rejects_localhost_official_url_400(client, make_user, make_entry):
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
def test_api_promote_rejects_private_ip_official_url_400(client, make_user, make_entry):
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
def test_api_promote_goods_entry_returns_400(client, make_user, make_entry):
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
def test_api_promote_other_users_entry_404(client, make_user, make_entry):
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
def test_api_promote_already_submitted_409(client, make_user, make_entry):
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
def test_promote_with_existing_draft_url_returns_field_error(client, make_user, make_entry, make_draft):
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
def test_api_promote_requires_authentication(client, make_user, make_entry):
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
def test_api_promote_is_rate_limited_per_user(client, make_user, make_entry):
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
