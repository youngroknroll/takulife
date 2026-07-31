"""Phase 2: VisitRecord는 Event(공식) 또는 PersonalEntry(비공식) 중 정확히
하나만 가리킬 수 있다. 모델 제약과 API either/or 검증(personal_entry 소유자
범위 포함)을 다룬다.
"""
import pytest
from django.db import IntegrityError, transaction

from archive.models import PersonalEntry, VisitRecord


# ---------------------------------------------------------------------------
# 모델 제약 — 대상은 정확히 하나여야 한다
# ---------------------------------------------------------------------------


@pytest.mark.domain
@pytest.mark.django_db
def test_비공식_장소를_대상으로_방문_기록을_생성하면_개인_항목이_연결된다(make_user):
    user = make_user(username="vr-pe")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="비공식 장소")

    record = VisitRecord.objects.create(
        user=user, personal_entry=entry, visited_on="2026-06-20"
    )

    assert record.event is None
    assert record.personal_entry == entry


@pytest.mark.domain
@pytest.mark.django_db
def test_방문_기록에_공식_행사와_비공식_장소를_동시에_지정하면_생성이_거부된다(make_user, make_event):
    user = make_user(username="vr-both")
    event = make_event(title="Official")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="P")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            VisitRecord.objects.create(
                user=user, event=event, personal_entry=entry, visited_on="2026-06-20"
            )


@pytest.mark.domain
@pytest.mark.django_db
def test_방문_기록에_대상을_지정하지_않으면_생성이_거부된다(make_user):
    user = make_user(username="vr-none")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            VisitRecord.objects.create(user=user, visited_on="2026-06-20")


# ---------------------------------------------------------------------------
# API — 둘 중 하나만 허용
# ---------------------------------------------------------------------------


@pytest.mark.web
@pytest.mark.django_db
def test_API로_비공식_장소를_대상으로_방문_기록을_생성하면_개인_항목이_저장된다(client, make_user):
    user = make_user(username="vr-api-pe")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="비공식 카페")

    client.force_login(user)
    response = client.post(
        "/api/visit-records/",
        {"personal_entry": entry.id, "visited_on": "2026-06-21", "short_review": "좋았다"},
        content_type="application/json",
    )

    assert response.status_code == 201
    data = response.json()
    assert data["personal_entry"] == entry.id
    assert data["event"] is None


@pytest.mark.web
@pytest.mark.django_db
def test_API로_공식_행사를_대상으로_방문_기록을_생성하면_행사가_저장된다(client, make_user, make_event):
    user = make_user(username="vr-api-ev")
    event = make_event(title="Official event")

    client.force_login(user)
    response = client.post(
        "/api/visit-records/",
        {"event": event.id, "visited_on": "2026-06-21"},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert response.json()["event"] == event.id


@pytest.mark.web
@pytest.mark.django_db
def test_API로_대상_없이_방문_기록_생성을_요청하면_거부된다(client, make_user):
    user = make_user(username="vr-api-none")

    client.force_login(user)
    response = client.post(
        "/api/visit-records/",
        {"visited_on": "2026-06-21"},
        content_type="application/json",
    )

    assert response.status_code == 400


@pytest.mark.web
@pytest.mark.django_db
def test_굿즈_개인_항목을_대상으로_방문_기록_생성을_요청하면_거부된다(client, make_user):
    """GOODS는 더 이상 유효한 아카이브 액션 대상이 아니다 (컬렉션 도메인
    설계안 §3-3) — 방문 기록에는 PLACE 개인 항목만 연결할 수 있다."""
    user = make_user(username="vr-api-goods")
    entry = PersonalEntry.objects.create(user=user, kind="goods", title="굿즈")

    client.force_login(user)
    response = client.post(
        "/api/visit-records/",
        {"personal_entry": entry.id, "visited_on": "2026-06-21"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not VisitRecord.objects.filter(personal_entry=entry).exists()


@pytest.mark.web
@pytest.mark.django_db
def test_타인의_개인_항목을_대상으로_방문_기록_생성을_요청하면_거부된다(client, make_user):
    user = make_user(username="vr-api-scope")
    other = make_user(username="vr-api-scope-other")
    theirs = PersonalEntry.objects.create(user=other, kind="place", title="Theirs")

    client.force_login(user)
    response = client.post(
        "/api/visit-records/",
        {"personal_entry": theirs.id, "visited_on": "2026-06-21"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not VisitRecord.objects.filter(personal_entry=theirs).exists()
