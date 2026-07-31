"""Phase 3: EventInterest(찜)와 UserEventStatus(방문예정)는 Event(공식) 또는
PersonalEntry(비공식) 중 정확히 하나만을 가리킬 수 있다.

모델 제약(정확히 하나 + 조건부 유일성)과 API의 이벤트/개인항목 양자택일 검증을
다루며, personal_entry의 소유자 범위 한정과 event 하위호환도 포함한다.
test_visit_record_subject.py(Phase 2)와 대응된다.
"""
import pytest
from django.db import IntegrityError, transaction

from archive.models import EventInterest, PersonalEntry, UserEventStatus


# ---------------------------------------------------------------------------
# EventInterest — 모델 제약
# ---------------------------------------------------------------------------


@pytest.mark.domain
@pytest.mark.django_db
def test_개인항목을_주체로_찜을_생성하면_이벤트는_없음으로_저장된다(make_user):
    user = make_user(username="ei-pe")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="비공식 장소")

    interest = EventInterest.objects.create(user=user, personal_entry=entry)

    assert interest.event is None
    assert interest.personal_entry == entry


@pytest.mark.domain
@pytest.mark.django_db
def test_이벤트와_개인항목을_동시에_지정해_찜을_생성하면_무결성_오류가_발생한다(make_user, make_event):
    user = make_user(username="ei-both")
    event = make_event(title="Official")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="P")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EventInterest.objects.create(user=user, event=event, personal_entry=entry)


@pytest.mark.domain
@pytest.mark.django_db
def test_주체를_지정하지_않고_찜을_생성하면_무결성_오류가_발생한다(make_user):
    user = make_user(username="ei-none")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EventInterest.objects.create(user=user)


@pytest.mark.domain
@pytest.mark.django_db
def test_같은_이벤트에_대한_찜을_중복_생성하면_무결성_오류가_발생한다(make_user, make_event):
    user = make_user(username="ei-ev-unique")
    event = make_event(title="E")

    EventInterest.objects.create(user=user, event=event)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EventInterest.objects.create(user=user, event=event)


@pytest.mark.domain
@pytest.mark.django_db
def test_같은_개인항목에_대한_찜을_중복_생성하면_무결성_오류가_발생한다(make_user):
    user = make_user(username="ei-pe-unique")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="P")

    EventInterest.objects.create(user=user, personal_entry=entry)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EventInterest.objects.create(user=user, personal_entry=entry)


# ---------------------------------------------------------------------------
# UserEventStatus — 모델 제약
# ---------------------------------------------------------------------------


@pytest.mark.domain
@pytest.mark.django_db
def test_개인항목을_주체로_상태를_생성하면_이벤트는_없음으로_저장된다(make_user):
    user = make_user(username="ues-pe")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="비공식 장소")

    status = UserEventStatus.objects.create(
        user=user, personal_entry=entry, status="planned"
    )

    assert status.event is None
    assert status.personal_entry == entry


@pytest.mark.domain
@pytest.mark.django_db
def test_이벤트와_개인항목을_동시에_지정해_상태를_생성하면_무결성_오류가_발생한다(make_user, make_event):
    user = make_user(username="ues-both")
    event = make_event(title="Official")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="P")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            UserEventStatus.objects.create(
                user=user, event=event, personal_entry=entry, status="planned"
            )


@pytest.mark.domain
@pytest.mark.django_db
def test_주체를_지정하지_않고_상태를_생성하면_무결성_오류가_발생한다(make_user):
    user = make_user(username="ues-none")

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            UserEventStatus.objects.create(user=user, status="planned")


@pytest.mark.domain
@pytest.mark.django_db
def test_같은_이벤트에_대한_상태를_중복_생성하면_무결성_오류가_발생한다(make_user, make_event):
    user = make_user(username="ues-ev-unique")
    event = make_event(title="E")

    UserEventStatus.objects.create(user=user, event=event, status="planned")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            UserEventStatus.objects.create(user=user, event=event, status="visited")


@pytest.mark.domain
@pytest.mark.django_db
def test_같은_개인항목에_대한_상태를_중복_생성하면_무결성_오류가_발생한다(make_user):
    user = make_user(username="ues-pe-unique")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="P")

    UserEventStatus.objects.create(user=user, personal_entry=entry, status="planned")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            UserEventStatus.objects.create(
                user=user, personal_entry=entry, status="visited"
            )


# ---------------------------------------------------------------------------
# EventInterest API — 이벤트/개인항목 양자택일
# ---------------------------------------------------------------------------


@pytest.mark.web
@pytest.mark.django_db
def test_개인항목_id로_찜_생성을_요청하면_201과_함께_이벤트는_없음으로_응답된다(client, make_user):
    user = make_user(username="ei-api-pe")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="비공식 카페")

    client.force_login(user)
    response = client.post(
        "/api/event-interests/",
        {"personal_entry": entry.id},
        content_type="application/json",
    )

    assert response.status_code == 201
    data = response.json()
    assert data["personal_entry"] == entry.id
    assert data["event"] is None


@pytest.mark.web
@pytest.mark.django_db
def test_이벤트_id로_찜_생성을_요청하면_기존과_동일하게_201로_응답된다(client, make_user, make_event):
    user = make_user(username="ei-api-ev")
    event = make_event(title="Official event")

    client.force_login(user)
    response = client.post(
        "/api/event-interests/",
        {"event": event.id},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert response.json()["event"] == event.id


@pytest.mark.web
@pytest.mark.django_db
def test_주체를_지정하지_않고_찜_생성을_요청하면_400으로_거부된다(client, make_user):
    user = make_user(username="ei-api-none")

    client.force_login(user)
    response = client.post(
        "/api/event-interests/",
        {},
        content_type="application/json",
    )

    assert response.status_code == 400


@pytest.mark.web
@pytest.mark.django_db
def test_타인_소유_개인항목으로_찜_생성을_요청하면_400으로_거부되고_저장되지_않는다(client, make_user):
    user = make_user(username="ei-api-scope")
    other = make_user(username="ei-api-scope-other")
    theirs = PersonalEntry.objects.create(user=other, kind="place", title="Theirs")

    client.force_login(user)
    response = client.post(
        "/api/event-interests/",
        {"personal_entry": theirs.id},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not EventInterest.objects.filter(personal_entry=theirs).exists()


@pytest.mark.web
@pytest.mark.django_db
def test_이미_찜한_개인항목에_다시_찜_생성을_요청하면_409로_거부된다(client, make_user):
    user = make_user(username="ei-api-dup")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="P")

    client.force_login(user)
    client.post(
        "/api/event-interests/",
        {"personal_entry": entry.id},
        content_type="application/json",
    )
    response = client.post(
        "/api/event-interests/",
        {"personal_entry": entry.id},
        content_type="application/json",
    )

    assert response.status_code == 409


# ---------------------------------------------------------------------------
# UserEventStatus API — 이벤트/개인항목 양자택일
# ---------------------------------------------------------------------------


@pytest.mark.web
@pytest.mark.django_db
def test_개인항목_id로_상태_생성을_요청하면_201과_함께_이벤트는_없음으로_응답된다(client, make_user):
    user = make_user(username="ues-api-pe")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="비공식 장소")

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"personal_entry": entry.id, "status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 201
    data = response.json()
    assert data["personal_entry"] == entry.id
    assert data["event"] is None
    assert data["status"] == "planned"


@pytest.mark.web
@pytest.mark.django_db
def test_이벤트_id로_상태_생성을_요청하면_기존과_동일하게_201로_응답된다(client, make_user, make_event):
    user = make_user(username="ues-api-ev")
    event = make_event(title="Official event")

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"event": event.id, "status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert response.json()["event"] == event.id


@pytest.mark.web
@pytest.mark.django_db
def test_주체를_지정하지_않고_상태_생성을_요청하면_400으로_거부된다(client, make_user):
    user = make_user(username="ues-api-none")

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 400


@pytest.mark.web
@pytest.mark.django_db
def test_타인_소유_개인항목으로_상태_생성을_요청하면_400으로_거부되고_저장되지_않는다(client, make_user):
    user = make_user(username="ues-api-scope")
    other = make_user(username="ues-api-scope-other")
    theirs = PersonalEntry.objects.create(user=other, kind="place", title="Theirs")

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"personal_entry": theirs.id, "status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not UserEventStatus.objects.filter(personal_entry=theirs).exists()


@pytest.mark.web
@pytest.mark.django_db
def test_굿즈_kind_개인항목으로_찜_생성을_요청하면_400으로_거부되고_저장되지_않는다(client, make_user):
    """GOODS는 더 이상 아카이브 행동의 대상이 아니다(컬렉션 도메인 설계안 §3-3) —
    PLACE 개인항목만 찜할 수 있다."""
    user = make_user(username="ei-api-goods")
    entry = PersonalEntry.objects.create(user=user, kind="goods", title="굿즈")

    client.force_login(user)
    response = client.post(
        "/api/event-interests/",
        {"personal_entry": entry.id},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not EventInterest.objects.filter(personal_entry=entry).exists()


@pytest.mark.web
@pytest.mark.django_db
def test_이미_상태가_있는_개인항목에_다시_상태_생성을_요청하면_409로_거부된다(client, make_user):
    user = make_user(username="ues-api-dup")
    entry = PersonalEntry.objects.create(user=user, kind="place", title="P")

    client.force_login(user)
    client.post(
        "/api/user-event-statuses/",
        {"personal_entry": entry.id, "status": "planned"},
        content_type="application/json",
    )
    response = client.post(
        "/api/user-event-statuses/",
        {"personal_entry": entry.id, "status": "visited"},
        content_type="application/json",
    )

    assert response.status_code == 409


@pytest.mark.web
@pytest.mark.django_db
def test_굿즈_kind_개인항목으로_상태_생성을_요청하면_400으로_거부되고_저장되지_않는다(client, make_user):
    """GOODS는 더 이상 아카이브 행동의 대상이 아니다(컬렉션 도메인 설계안 §3-3) —
    PLACE 개인항목만 상태를 가질 수 있다."""
    user = make_user(username="ues-api-goods")
    entry = PersonalEntry.objects.create(user=user, kind="goods", title="굿즈")

    client.force_login(user)
    response = client.post(
        "/api/user-event-statuses/",
        {"personal_entry": entry.id, "status": "planned"},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not UserEventStatus.objects.filter(personal_entry=entry).exists()
