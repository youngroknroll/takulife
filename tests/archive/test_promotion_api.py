"""API — POST /api/personal-entries/<id>/promote/

비공개 PersonalEntry를 관리자 드래프트 검수 파이프라인으로 승격한다(오케스트레이션
자체는 core.promotion.promote_personal_entry 참고, tests/archive/
test_promotion_service.py에서 직접 테스트됨). 관리자가 시드된 드래프트를 승인해
공개 Event로 만들기 전까지 항목은 비공개로 유지된다.
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
    """goods 항목은 승격할 수 없다(컬렉션 도메인 설계안 §3-3) — 뷰는
    PromotionKindNotAllowedError를 처리되지 않은 500이 아니라 제어된 400으로
    변환해야 한다."""
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
    user = make_user()
    entry = make_entry(user, kind="place", title="제보 대상")
    # 이미 이 공식 URL을 가진 드래프트가 있다 → 승격은 중복으로 처리된다
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
# 속도 제한 — 검수 큐가 플러딩되지 않도록 한다
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.slow
def test_일일_승격_한도를_초과하면_429로_제한된다(client, make_user, make_entry):
    """일일 승격 한도를 넘으면 이후 승격 요청은 429로 제한된다."""
    user = make_user(username="api-promo-flood")
    client.force_login(user)

    # 일일 한도 20건: 20번째까지는 성공하고 21번째부터 제한된다
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
