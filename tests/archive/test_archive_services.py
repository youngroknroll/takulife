"""아카이브 서비스 계층 테스트 — HTTP 없이 서비스를 직접 호출한다."""
import uuid

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError

from archive.models import CollectionItem, PersonalEntry, VisitRecord
from archive.services import (
    DuplicateUserEventStatusError,
    MAX_PHOTOS_PER_RECORD,
    PhotoLimitExceededError,
    create_collection_item,
    create_personal_entry,
    create_user_event_status,
    create_visit_record,
    create_visit_record_photo,
    update_collection_item,
)
from events.models import Event


@pytest.mark.domain
@pytest.mark.django_db
def test_이벤트를_대상으로_상태를_생성하면_사용자와_이벤트와_상태값이_그대로_저장된다(make_user, make_event):
    user = make_user(email="service-user@example.com", username="service-user")
    event = make_event(
        title="Published event",
        publish_status=Event.PublishStatus.PUBLISHED,
    )

    created = create_user_event_status(user=user, event=event, status="planned")

    assert created.user_id == user.id
    assert created.event_id == event.id
    assert created.status == "planned"


@pytest.mark.domain
@pytest.mark.django_db
def test_DB_무결성_오류가_발생하면_상태_생성은_중복_예외로_변환된다(monkeypatch, make_user, make_event):
    user = make_user(email="status-user@example.com", username="status-user")
    event = make_event(title="Published event", publish_status=Event.PublishStatus.PUBLISHED)

    def raise_integrity_error(**kwargs):
        raise IntegrityError("duplicate")

    monkeypatch.setattr("archive.services.UserEventStatus.objects.create", raise_integrity_error)

    with pytest.raises(DuplicateUserEventStatusError):
        create_user_event_status(user=user, event=event, status="planned")


@pytest.mark.contract
@pytest.mark.django_db
def test_방문기록_사진을_추가하면_동시_업로드_방지를_위해_부모_방문기록_행을_잠근다(make_user, make_event, png_bytes, settings, tmp_path, monkeypatch, make_visit):
    """count-then-create는 원자적이어야 하며 부모 VisitRecord 행을 잠가야
    한다(select_for_update) — 그래야 동시 업로드 두 건이 모두 개수 검사를 통과해
    MAX_PHOTOS_PER_RECORD를 넘기는 일이 없다."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")

    calls = []
    original_select_for_update = VisitRecord.objects.select_for_update

    def spy_select_for_update(*args, **kwargs):
        calls.append((args, kwargs))
        return original_select_for_update(*args, **kwargs)

    monkeypatch.setattr(VisitRecord.objects, "select_for_update", spy_select_for_update)

    photo = create_visit_record_photo(
        visit_record=record,
        image=SimpleUploadedFile("photo.png", png_bytes(), content_type="image/png"),
    )

    assert photo.visit_record_id == record.id
    assert calls, "create_visit_record_photo must select_for_update the parent VisitRecord row"


@pytest.mark.domain
@pytest.mark.django_db
def test_방문기록_사진이_상한에_도달하면_추가_업로드는_예외로_거부된다(make_user, make_event, png_bytes, settings, tmp_path, make_visit, make_visit_photo):
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user()
    event = make_event()
    record = make_visit(user, event=event, visited_on="2026-05-26")
    png_data = png_bytes()
    for i in range(5):
        make_visit_photo(record, filename=f"photo-{i}.png")

    with pytest.raises(PhotoLimitExceededError):
        create_visit_record_photo(
            visit_record=record,
            image=SimpleUploadedFile("extra.png", png_data, content_type="image/png"),
        )


@pytest.mark.domain
@pytest.mark.django_db
def test_상한을_채운_마지막_사진과_같은_클라이언트_토큰으로_재시도하면_상한_예외_없이_기존_사진이_반환된다(
    make_user, make_event, make_visit, make_visit_photo, png_bytes, settings, tmp_path
):
    """bfcache 중복 생성 트랙(INTG-BE-04-VRP): MAX_PHOTOS_PER_RECORD를 채운 바로 그
    사진에 대한 응답 유실 후 재시도가 이 멱등성 키가 고치려는 실제 실패
    시나리오다 — 클라이언트가 첫 응답을 못 받고 같은 client_token으로
    재요청한다. 현재 create_visit_record_photo는 count-then-create 상한
    검사를 재전송 조회보다 먼저 하므로, 이 재시도는 "사진 한 장 초과"로
    오분류되어 이미 존재하는 행을 반환하는 대신 PhotoLimitExceededError로
    거부된다. 이 테스트는 수정 후 기대 동작(예외 없음, 같은 행 반환, 개수
    불변)을 문서화하며, 상한 검사/재전송 조회 순서 결함이 고쳐지기 전까지는
    단언 실패가 아닌 PhotoLimitExceededError로 실패할 것으로 예상된다."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user(username="vrp-service-limit-replay")
    event = make_event(title="상한 재시도 확인 이벤트")
    record = make_visit(user, event=event, visited_on="2026-01-01")
    token = uuid.uuid4()

    # Given: 상한이 이미 찼고, 마지막 직전까지의 사진은 토큰 없이 생성됐으며,
    # 상한을 채우는 마지막 사진만 검증 대상 토큰을 갖는다.
    for i in range(MAX_PHOTOS_PER_RECORD - 1):
        make_visit_photo(record, filename=f"photo-{i}.png")
    last = create_visit_record_photo(
        visit_record=record,
        image=SimpleUploadedFile("last.png", png_bytes(), content_type="image/png"),
        client_token=token,
    )
    assert record.photos.count() == MAX_PHOTOS_PER_RECORD

    # When: 클라이언트가 `last`의 응답을 받지 못해 같은 요청을(같은 토큰으로)
    # 그대로 재시도한다.
    retried = create_visit_record_photo(
        visit_record=record,
        image=SimpleUploadedFile("retry.png", png_bytes(), content_type="image/png"),
        client_token=token,
    )

    # Then: PhotoLimitExceededError 없이 기존 행이 그대로 반환되고, 기록의
    # 사진 개수는 상한에서 늘어나지 않는다.
    assert retried.id == last.id
    assert record.photos.count() == MAX_PHOTOS_PER_RECORD


@pytest.mark.domain
@pytest.mark.django_db
def test_같은_방문기록에_같은_클라이언트_토큰으로_사진_생성을_두_번_요청하면_행은_하나만_생성되고_동일한_id가_반환된다(
    make_user, make_event, make_visit, png_bytes, settings, tmp_path
):
    """bfcache 중복 생성 트랙(INTG-BE-01-VRP): 같은 client_token으로 사진 업로드
    요청을 재전송해도(예: bfcache 복원 페이지의 재제출, 또는
    MAX_PHOTOS_PER_RECORD 직전 응답 유실 재시도) 두 번째 행이 생성돼선 안
    된다 — 두 번째 호출은 원본 사진 행을 그대로 반환하는 멱등 재전송이어야
    하며, 이미지가 원본을 덮어쓰는 두 번째 생성이 되어선 안 된다. 위
    VisitRecord 멱등성 가드(INTG-BE-01-VR)와 대응하되 (user, client_token)이
    아닌 (visit_record, client_token) 범위다 — 범위 경계 증명은 아래
    INTG-BE-03-VRP 참고."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user(username="vrp-service-idempotent-token")
    event = make_event(title="사진 멱등성 확인 이벤트")
    record = make_visit(user, event=event, visited_on="2026-01-01")
    token = uuid.uuid4()
    first_bytes = png_bytes(color=(255, 0, 0))
    second_bytes = png_bytes(color=(0, 255, 0))

    # Given: 이 토큰을 가진 사진이 이 기록에 아직 없고, MAX_PHOTOS_PER_RECORD
    # 상한 가드가 끼어들지 않을 만큼 여유가 있다.
    assert not record.photos.filter(client_token=token).exists()

    # When: 같은 기록에 같은 client_token으로 두 번 요청하고, 두 번째(재전송)
    # 호출은 다른 이미지를 보낸다.
    first = create_visit_record_photo(
        visit_record=record,
        image=SimpleUploadedFile("first.png", first_bytes, content_type="image/png"),
        client_token=token,
    )
    second = create_visit_record_photo(
        visit_record=record,
        image=SimpleUploadedFile("second.png", second_bytes, content_type="image/png"),
        client_token=token,
    )

    # Then: 행은 정확히 하나이고 두 호출 모두 같은 행을 반환하며, 재전송의
    # 이미지가 원본 파일을 덮어쓰지 않았다.
    assert record.photos.filter(client_token=token).count() == 1
    assert first.id == second.id
    first.refresh_from_db()
    stored_bytes = first.image.read()
    assert stored_bytes == first_bytes
    assert stored_bytes != second_bytes


@pytest.mark.domain
@pytest.mark.django_db
def test_같은_사용자의_서로_다른_방문기록에_같은_클라이언트_토큰으로_사진을_생성하면_각각_독립적으로_생성된다(
    make_user, make_event, make_visit, png_bytes, settings, tmp_path
):
    """bfcache 중복 생성 트랙(INTG-BE-03-VRP): PersonalEntry/CollectionItem/
    VisitRecord의 멱등성 키는 (user, client_token) 범위지만, 사진의 멱등성
    키는 (visit_record, client_token) 범위다 — 사진은 VisitRecord의 자식
    행이지 사용자 소유 애그리게이트 루트가 아니고, 한 사용자가 여러 기록에
    걸쳐 많은 사진을 만든다. 같은 사용자가 소유한 서로 다른 두 기록이 같은
    클라이언트 생성 uuid4를 재전송하면 각각 자기 사진 행을 가져야 하며, 어느
    기록의 생성도 같은 토큰의 다른 기록 사진 존재로 인해 단축되어선 안
    된다(기록 간 존재 오라클 없음)."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user(username="vrp-service-token-scope-user")
    event = make_event(title="사진 스코프 확인 이벤트")
    record_a = make_visit(user, event=event, visited_on="2026-01-01")
    record_b = make_visit(user, event=event, visited_on="2026-01-02")
    token = uuid.uuid4()

    photo_a = create_visit_record_photo(
        visit_record=record_a,
        image=SimpleUploadedFile("a.png", png_bytes(), content_type="image/png"),
        client_token=token,
    )
    photo_b = create_visit_record_photo(
        visit_record=record_b,
        image=SimpleUploadedFile("b.png", png_bytes(), content_type="image/png"),
        client_token=token,
    )

    assert photo_a.id != photo_b.id
    assert record_a.photos.filter(client_token=token).count() == 1
    assert record_b.photos.filter(client_token=token).count() == 1


@pytest.mark.domain
@pytest.mark.django_db
def test_비공식_항목을_생성하면_입력한_필드가_그대로_저장된다(make_user):
    user = make_user(username="pe-service")
    entry = create_personal_entry(
        user=user, kind="place", title="비공식 팝업", location_name="성수"
    )

    assert entry.pk is not None
    assert entry.user == user
    assert entry.location_name == "성수"


@pytest.mark.domain
@pytest.mark.django_db
def test_굿즈_kind로_비공식_항목_생성을_시도하면_거부된다(make_user):
    """GOODS는 더 이상 PersonalEntry로 생성할 수 없다(컬렉션 도메인 계획 §3-3)
    — 굿즈는 전용 CollectionItem 도메인에 산다."""
    user = make_user(username="pe-service-goods")

    with pytest.raises(ValidationError):
        create_personal_entry(user=user, kind="goods", title="차단되어야 할 굿즈")


@pytest.mark.domain
@pytest.mark.django_db
def test_같은_사용자가_같은_클라이언트_토큰으로_비공식_항목_생성을_두_번_요청하면_행은_하나만_생성되고_동일한_id가_반환된다(make_user):
    """bfcache 중복 생성 트랙(INTG-BE-01-PE): 같은 client_token으로 생성 요청을
    재전송해도(예: bfcache 복원 페이지의 재제출) 두 번째 행이 생성돼선 안
    된다 — 두 번째 호출은 원본 행을 그대로 반환하는 멱등 재전송이어야 하며,
    재전송 자체의 필드 값으로 새로 생성돼선 안 된다. 아래 CollectionItem
    멱등성 가드(INTG-BE-01-CI)와 대응된다."""
    user = make_user(username="pe-service-idempotent-token")
    token = uuid.uuid4()

    # Given: 이 사용자가 이 토큰으로 소유한 PersonalEntry가 아직 없다.
    assert not PersonalEntry.objects.filter(user=user, client_token=token).exists()

    # When: 같은 사용자가 같은 client_token으로 두 번 요청하고, 두 번째
    # (재전송) 호출은 다른 제목을 보낸다.
    first = create_personal_entry(
        user=user, kind="place", title="원래 제목", client_token=token
    )
    second = create_personal_entry(
        user=user, kind="place", title="다른 제목", client_token=token
    )

    # Then: 행은 정확히 하나이고 두 호출 모두 같은 행을 반환하며, 재전송의
    # 페이로드가 원본 제목을 덮어쓰지 않았다.
    assert PersonalEntry.objects.filter(user=user, client_token=token).count() == 1
    assert first.id == second.id
    first.refresh_from_db()
    assert first.title == "원래 제목"


@pytest.mark.domain
@pytest.mark.django_db
def test_서로_다른_사용자가_같은_클라이언트_토큰으로_비공식_항목을_생성하면_각각_독립적으로_생성된다(make_user):
    """bfcache 중복 생성 트랙(INTG-BE-03-PE): 멱등성 키는 client_token 단독이
    아니라 (user, client_token) 범위다 — 서로 다른 두 사용자가 같은 클라이언트
    생성 uuid4를 재전송하면(버그나 공유 클라이언트 라이브러리 인스턴스 등)
    각각 자기 행을 가져야 하며, 어느 사용자의 생성도 같은 토큰의 다른 사용자
    기존 행으로 인해 단축되어선 안 된다(사용자 간 존재 오라클 없음). 아래
    CollectionItem 교차 사용자 테스트(INTG-BE-03-CI)와 대응된다."""
    user_a = make_user(username="pe-service-token-user-a")
    user_b = make_user(username="pe-service-token-user-b")
    token = uuid.uuid4()

    item_a = create_personal_entry(
        user=user_a, kind="place", title="사용자 A 항목", client_token=token
    )
    item_b = create_personal_entry(
        user=user_b, kind="place", title="사용자 B 항목", client_token=token
    )

    assert item_a.id != item_b.id
    assert PersonalEntry.objects.filter(client_token=token).count() == 2
    assert PersonalEntry.objects.filter(user=user_a, client_token=token).count() == 1
    assert PersonalEntry.objects.filter(user=user_b, client_token=token).count() == 1


@pytest.mark.domain
@pytest.mark.django_db
def test_클라이언트_토큰_없이_동일한_내용으로_비공식_항목_생성을_두_번_요청하면_행이_각각_생성된다(make_user):
    """bfcache 중복 생성 트랙(INTG-BE-02-PE): 멱등성 가드는 (user, client_token)
    범위다 — client_token을 전혀 넘기지 않는 호출자(예: 제목이 같은 진짜
    별개의 정당한 항목 두 개)는 한 행으로 합쳐지면 안 된다. INTG-BE-01-PE에서
    추가한 조건부 UniqueConstraint가 멱등성 키가 없을 때 정당한 중복 항목을
    과잉 차단하지 않음을 증명한다. 위 CollectionItem 무토큰
    테스트(INTG-BE-02-CI)와 대응된다."""
    user = make_user(username="pe-service-no-token-duplicate")

    first = create_personal_entry(user=user, kind="place", title="같은 이름 장소")
    second = create_personal_entry(user=user, kind="place", title="같은 이름 장소")

    assert first.id != second.id
    assert PersonalEntry.objects.filter(user=user, title="같은 이름 장소").count() == 2


# ---------------------------------------------------------------------------
# create_collection_item (PR-C1)
# ---------------------------------------------------------------------------


@pytest.mark.domain
@pytest.mark.django_db
def test_방문기록을_연결해_컬렉션_아이템을_생성하면_이벤트가_방문기록의_이벤트로_자동_동기화된다(make_user, make_event, make_visit):
    user = make_user(username="ci-service-sync")
    event = make_event(title="싱크할 이벤트")
    visit_record = make_visit(user, event=event, visited_on="2026-01-01")

    item = create_collection_item(
        user=user, name="이벤트 한정 굿즈", visit_record=visit_record
    )

    assert item.visit_record_id == visit_record.id
    assert item.event_id == event.id


@pytest.mark.domain
@pytest.mark.django_db
def test_방문기록과_충돌하는_이벤트를_함께_지정해_생성해도_방문기록의_이벤트가_우선한다(
    make_user, make_event, make_visit
):
    user = make_user(username="ci-service-override")
    visit_event = make_event(title="방문 이벤트")
    conflicting_event = make_event(title="다른 이벤트")
    visit_record = make_visit(user, event=visit_event, visited_on="2026-01-01")

    item = create_collection_item(
        user=user,
        name="충돌 굿즈",
        visit_record=visit_record,
        event=conflicting_event,
    )

    assert item.event_id == visit_event.id


@pytest.mark.domain
@pytest.mark.django_db
def test_수량이_음수인_컬렉션_아이템_생성은_DB_저장_전에_거부된다(make_user):
    user = make_user(username="ci-service-neg-qty")

    with pytest.raises(ValidationError) as exc_info:
        create_collection_item(user=user, name="음수 수량", quantity=-1)

    # 수량이 음수면 기본 tradeable_quantity(0)도 초과하므로
    # tradeable_quantity>quantity elif도 함께 발동한다 — 이 테스트를 CP1
    # 분기로만 좁히기 위해 quantity 키의 메시지만 검사한다.
    assert exc_info.value.message_dict["quantity"] == ["quantity는 0 이상이어야 합니다."]


@pytest.mark.domain
@pytest.mark.django_db
def test_교환가능_수량이_음수인_컬렉션_아이템_생성은_DB_저장_전에_거부된다(make_user):
    user = make_user(username="ci-service-neg-tradeable")

    with pytest.raises(ValidationError) as exc_info:
        create_collection_item(
            user=user, name="음수 교환 수량", quantity=5, tradeable_quantity=-1
        )

    assert exc_info.value.message_dict == {
        "tradeable_quantity": ["tradeable_quantity는 0 이상이어야 합니다."]
    }


@pytest.mark.domain
@pytest.mark.django_db
def test_교환가능_수량이_보유_수량을_초과하는_생성은_거부된다(make_user):
    user = make_user(username="ci-service-tradeable-exceeds")

    with pytest.raises(ValidationError) as exc_info:
        create_collection_item(
            user=user, name="초과 교환 수량", quantity=1, tradeable_quantity=2
        )

    assert exc_info.value.message_dict == {
        "tradeable_quantity": ["tradeable_quantity는 quantity 이하여야 합니다."]
    }


@pytest.mark.domain
@pytest.mark.django_db
def test_타인_소유의_방문기록을_연결해_생성을_시도하면_거부된다(
    make_user, make_event, make_visit
):
    owner = make_user(username="ci-service-visit-owner")
    other = make_user(username="ci-service-other-user")
    event = make_event(title="타인 방문 이벤트")
    visit_record = make_visit(owner, event=event, visited_on="2026-01-01")

    with pytest.raises(ValidationError) as exc_info:
        create_collection_item(user=other, name="타인 소유 위반", visit_record=visit_record)

    assert exc_info.value.message_dict == {
        "visit_record": ["visit_record는 요청한 사용자의 소유여야 합니다."]
    }


@pytest.mark.domain
@pytest.mark.django_db
def test_비공식_개인항목에_연결된_방문기록으로_생성하면_이벤트는_없음으로_동기화된다(
    make_user, make_entry, make_visit, make_event
):
    user = make_user(username="ci-service-unofficial-visit")
    personal_entry = make_entry(user)
    visit_record = make_visit(user, personal_entry=personal_entry, visited_on="2026-01-01")
    conflicting_event = make_event(title="무시되어야 할 이벤트")

    item = create_collection_item(
        user=user,
        name="비공식 방문 굿즈",
        visit_record=visit_record,
        event=conflicting_event,
    )

    assert item.event_id is None


@pytest.mark.domain
@pytest.mark.django_db
def test_공개범위를_지정하지_않고_생성하면_기본값은_비공개이다(make_user):
    user = make_user(username="ci-service-visibility-default")

    item = create_collection_item(user=user, name="기본 공개범위 확인")

    assert item.visibility == "private"


@pytest.mark.domain
@pytest.mark.django_db
def test_같은_사용자가_같은_클라이언트_토큰으로_컬렉션_항목_생성을_두_번_요청하면_행은_하나만_생성되고_동일한_id가_반환된다(make_user):
    """bfcache 중복 생성 트랙(INTG-BE-01-CI): 같은 client_token으로 생성 요청을
    재전송해도(예: bfcache 복원 페이지의 재제출) 두 번째 행이 생성돼선 안
    된다 — 두 번째 호출은 원본 행을 그대로 반환하는 멱등 재전송이어야 하며,
    재전송 자체의 필드 값으로 새로 생성돼선 안 된다."""
    user = make_user(username="ci-service-idempotent-token")
    token = uuid.uuid4()

    # Given: 이 사용자가 이 토큰으로 소유한 CollectionItem이 아직 없다.
    assert not CollectionItem.objects.filter(user=user, client_token=token).exists()

    # When: 같은 사용자가 같은 client_token으로 두 번 요청하고, 두 번째
    # (재전송) 호출은 다른 필드 값을 보낸다.
    first = create_collection_item(user=user, name="원래 이름", client_token=token)
    second = create_collection_item(user=user, name="다른 이름", client_token=token)

    # Then: 행은 정확히 하나이고 두 호출 모두 같은 행을 반환하며, 재전송의
    # 페이로드가 원본 이름을 덮어쓰지 않았다.
    assert CollectionItem.objects.filter(user=user, client_token=token).count() == 1
    assert first.id == second.id
    first.refresh_from_db()
    assert first.name == "원래 이름"


@pytest.mark.domain
@pytest.mark.django_db
def test_클라이언트_토큰_없이_동일한_내용으로_컬렉션_항목_생성을_두_번_요청하면_행이_각각_생성된다(make_user):
    """bfcache 중복 생성 트랙(INTG-BE-02-CI): 멱등성 가드는 (user, client_token)
    범위다 — client_token을 전혀 넘기지 않는 호출자(예: 같은 굿즈의 진짜
    별개인 정당한 구매 두 건)는 한 행으로 합쳐지면 안 된다. INTG-BE-01-CI에서
    추가한 UniqueConstraint/조회 로직이 멱등성 키가 없을 때 정당한 중복
    소유를 과잉 차단하지 않음을 증명한다."""
    user = make_user(username="ci-service-no-token-duplicate")

    first = create_collection_item(user=user, name="같은 이름 굿즈")
    second = create_collection_item(user=user, name="같은 이름 굿즈")

    assert first.id != second.id
    assert CollectionItem.objects.filter(user=user, name="같은 이름 굿즈").count() == 2


@pytest.mark.domain
@pytest.mark.django_db
def test_서로_다른_사용자가_같은_클라이언트_토큰으로_컬렉션_항목을_생성하면_각각_독립적으로_생성된다(make_user):
    """bfcache 중복 생성 트랙(INTG-BE-03-CI): 멱등성 키는 client_token 단독이
    아니라 (user, client_token) 범위다 — 서로 다른 두 사용자가 같은 클라이언트
    생성 uuid4를 재전송하면(버그나 공유 클라이언트 라이브러리 인스턴스 등)
    각각 자기 행을 가져야 하며, 어느 사용자의 생성도 같은 토큰의 다른 사용자
    기존 행으로 인해 단축되어선 안 된다(사용자 간 존재 오라클 없음)."""
    user_a = make_user(username="ci-service-token-user-a")
    user_b = make_user(username="ci-service-token-user-b")
    token = uuid.uuid4()

    item_a = create_collection_item(user=user_a, name="사용자 A 굿즈", client_token=token)
    item_b = create_collection_item(user=user_b, name="사용자 B 굿즈", client_token=token)

    assert item_a.id != item_b.id
    assert CollectionItem.objects.filter(client_token=token).count() == 2
    assert CollectionItem.objects.filter(user=user_a, client_token=token).count() == 1
    assert CollectionItem.objects.filter(user=user_b, client_token=token).count() == 1


# ---------------------------------------------------------------------------
# create_visit_record (bfcache 멱등성)
# ---------------------------------------------------------------------------


@pytest.mark.domain
@pytest.mark.django_db
def test_같은_사용자가_같은_클라이언트_토큰으로_방문_기록_생성을_두_번_요청하면_행은_하나만_생성되고_동일한_id가_반환된다(
    make_user, make_event
):
    """bfcache 중복 생성 트랙(INTG-BE-01-VR): 같은 client_token으로 방문 기록
    생성 요청을 재전송해도(예: bfcache 복원 페이지의 재제출) 두 번째 행이
    생성돼선 안 된다 — 두 번째 호출은 원본 행을 그대로 반환하는 멱등
    재전송이어야 하며, 재전송 자체의 필드 값으로 새로 생성돼선 안 된다. 위
    CollectionItem 멱등성 가드(INTG-BE-01-CI)와 대응된다."""
    user = make_user(username="vr-service-idempotent-token")
    event = make_event(title="멱등성 확인 이벤트")
    token = uuid.uuid4()

    # Given: 이 사용자가 이 토큰으로 소유한 VisitRecord가 아직 없다.
    assert not VisitRecord.objects.filter(user=user, client_token=token).exists()

    # When: 같은 사용자가 같은 client_token으로 두 번 요청하고, 두 번째
    # (재전송) 호출은 다른 short_review를 보낸다.
    first = create_visit_record(
        user=user,
        event=event,
        visited_on="2026-01-01",
        short_review="원래 리뷰",
        client_token=token,
    )
    second = create_visit_record(
        user=user,
        event=event,
        visited_on="2026-01-01",
        short_review="다른 리뷰",
        client_token=token,
    )

    # Then: 행은 정확히 하나이고 두 호출 모두 같은 행을 반환하며, 재전송의
    # 페이로드가 원본 short_review를 덮어쓰지 않았다.
    assert VisitRecord.objects.filter(user=user, client_token=token).count() == 1
    assert first.id == second.id
    first.refresh_from_db()
    assert first.short_review == "원래 리뷰"


@pytest.mark.domain
@pytest.mark.django_db
def test_클라이언트_토큰_없이_동일한_내용으로_방문_기록_생성을_두_번_요청하면_행이_각각_생성된다(
    make_user, make_event
):
    """bfcache 중복 생성 트랙(INTG-BE-02-VR): 멱등성 가드는 (user, client_token)
    범위다 — client_token을 전혀 넘기지 않는 호출자(예: 같은 이벤트에 대한
    진짜 별개의 방문 기록 제출 두 건)는 한 행으로 합쳐지면 안 된다.
    INTG-BE-01-VR에서 추가한 UniqueConstraint/조회 로직이 멱등성 키가 없을
    때 정당한 중복 방문 기록을 과잉 차단하지 않음을 증명한다. 위
    CollectionItem 무토큰 테스트(INTG-BE-02-CI)와 대응된다."""
    user = make_user(username="vr-service-no-token-duplicate")
    event = make_event(title="토큰 없는 중복 확인 이벤트")

    first = create_visit_record(user=user, event=event, visited_on="2026-01-01")
    second = create_visit_record(user=user, event=event, visited_on="2026-01-01")

    assert first.id != second.id
    assert VisitRecord.objects.filter(user=user, event=event).count() == 2


@pytest.mark.domain
@pytest.mark.django_db
def test_서로_다른_사용자가_같은_클라이언트_토큰으로_방문_기록을_생성하면_각각_독립적으로_생성된다(
    make_user, make_event
):
    """bfcache 중복 생성 트랙(INTG-BE-03-VR): 멱등성 키는 client_token 단독이
    아니라 (user, client_token) 범위다 — 서로 다른 두 사용자가 같은 클라이언트
    생성 uuid4를 재전송하면(버그나 공유 클라이언트 라이브러리 인스턴스 등)
    각각 자기 행을 가져야 하며, 어느 사용자의 생성도 같은 토큰의 다른 사용자
    기존 행으로 인해 단축되어선 안 된다(사용자 간 존재 오라클 없음). 위
    CollectionItem 교차 사용자 토큰 테스트(INTG-BE-03-CI)와 대응된다."""
    user_a = make_user(username="vr-service-token-user-a")
    user_b = make_user(username="vr-service-token-user-b")
    event = make_event(title="교차 사용자 토큰 확인 이벤트")
    token = uuid.uuid4()

    record_a = create_visit_record(
        user=user_a, event=event, visited_on="2026-01-01", client_token=token
    )
    record_b = create_visit_record(
        user=user_b, event=event, visited_on="2026-01-01", client_token=token
    )

    assert record_a.id != record_b.id
    assert VisitRecord.objects.filter(client_token=token).count() == 2
    assert VisitRecord.objects.filter(user=user_a, client_token=token).count() == 1
    assert VisitRecord.objects.filter(user=user_b, client_token=token).count() == 1


# ---------------------------------------------------------------------------
# update_collection_item (PR-C5)
# ---------------------------------------------------------------------------


@pytest.mark.domain
@pytest.mark.django_db
def test_이름과_메모를_수정하면_컬렉션_아이템에_반영되어_저장된다(make_user):
    user = make_user(username="ci-update-simple")
    item = create_collection_item(user=user, name="원래 이름", memo="원래 메모")

    updated = update_collection_item(item=item, name="바뀐 이름", memo="바뀐 메모")

    item.refresh_from_db()
    assert updated.name == "바뀐 이름"
    assert item.name == "바뀐 이름"
    assert item.memo == "바뀐 메모"


@pytest.mark.domain
@pytest.mark.django_db
def test_수량만_수정해도_기존_교환가능_수량과_병합해_역전되면_거부된다(make_user):
    """quantity만 보내는 부분 PATCH도 *기존* tradeable_quantity와 대조해
    검사해야 한다 — payload에 tradeable을 빼는 것으로 불변식을 우회할 수
    없다(컬렉션 도메인 설계 계획 §5 인수 기준 3)."""
    user = make_user(username="ci-update-merge-guard")
    item = create_collection_item(
        user=user, name="병합 가드", quantity=5, tradeable_quantity=3
    )

    with pytest.raises(ValidationError):
        update_collection_item(item=item, quantity=1)

    item.refresh_from_db()
    assert item.quantity == 5


@pytest.mark.domain
@pytest.mark.django_db
def test_수량을_음수로_수정하면_기존값과_병합한_뒤에도_거부된다(make_user):
    """update_collection_item의 quantity<0 분기는 이 PR 전에는 전용
    커버리지가 없었다 — CP1은 create_collection_item의 대응 검사만 다뤘다."""
    user = make_user(username="ci-update-neg-qty")
    item = create_collection_item(user=user, name="음수 수량 수정")

    with pytest.raises(ValidationError) as exc_info:
        update_collection_item(item=item, quantity=-1)

    # 위 생성 경로 테스트와 같은 동시 발동이다: 병합된 quantity가 음수면
    # 기존 tradeable_quantity(0)도 초과하므로 quantity 키의 메시지만 검사한다.
    assert exc_info.value.message_dict["quantity"] == ["quantity는 0 이상이어야 합니다."]
    item.refresh_from_db()
    assert item.quantity == 1


@pytest.mark.domain
@pytest.mark.django_db
def test_교환가능_수량을_음수로_수정하면_거부된다(make_user):
    """update_collection_item의 tradeable_quantity<0 분기는 이 PR 전에는
    전용 커버리지가 없었다 — CP2는 create_collection_item의 대응 검사만
    다뤘다."""
    user = make_user(username="ci-update-neg-tradeable")
    item = create_collection_item(user=user, name="음수 교환 수량 수정", quantity=5)

    with pytest.raises(ValidationError) as exc_info:
        update_collection_item(item=item, tradeable_quantity=-1)

    assert exc_info.value.message_dict == {
        "tradeable_quantity": ["tradeable_quantity는 0 이상이어야 합니다."]
    }
    item.refresh_from_db()
    assert item.tradeable_quantity == 0


@pytest.mark.domain
@pytest.mark.django_db
def test_교환가능_수량을_보유_수량보다_크게_수정하면_거부된다(make_user):
    user = make_user(username="ci-update-direct-exceed")
    item = create_collection_item(user=user, name="직접 초과", quantity=5)

    with pytest.raises(ValidationError) as exc_info:
        update_collection_item(item=item, tradeable_quantity=10)

    assert exc_info.value.message_dict == {
        "tradeable_quantity": ["tradeable_quantity는 quantity 이하여야 합니다."]
    }
    item.refresh_from_db()
    assert item.tradeable_quantity == 0


@pytest.mark.domain
@pytest.mark.django_db
def test_타인_소유의_방문기록으로_수정을_시도하면_거부된다(
    make_user, make_event, make_visit
):
    owner = make_user(username="ci-update-visit-owner")
    other = make_user(username="ci-update-other-user")
    item = create_collection_item(user=other, name="타인 소유 수정 시도")
    event = make_event(title="타인 방문 이벤트")
    visit_record = make_visit(owner, event=event, visited_on="2026-01-01")

    with pytest.raises(ValidationError) as exc_info:
        update_collection_item(item=item, visit_record=visit_record)

    assert exc_info.value.message_dict == {
        "visit_record": ["visit_record는 아이템 소유자의 소유여야 합니다."]
    }
    item.refresh_from_db()
    assert item.visit_record_id is None


@pytest.mark.domain
@pytest.mark.django_db
def test_방문기록과_충돌하는_이벤트를_함께_수정해도_방문기록의_이벤트가_우선한다(
    make_user, make_event, make_visit
):
    user = make_user(username="ci-update-override")
    visit_event = make_event(title="방문 이벤트")
    conflicting_event = make_event(title="다른 이벤트")
    visit_record = make_visit(user, event=visit_event, visited_on="2026-01-01")
    item = create_collection_item(user=user, name="충돌 수정")

    updated = update_collection_item(
        item=item, visit_record=visit_record, event=conflicting_event
    )

    assert updated.event_id == visit_event.id


@pytest.mark.domain
@pytest.mark.django_db
def test_방문기록이_이미_연결된_아이템의_이벤트만_불일치하게_수정하면_거부된다(
    make_user, make_event, make_visit
):
    """full_clean() 연결(§6-b 지연, 컬렉션 도메인 설계 계획 §3-1 FK 쌍
    불변식): visit_record가 이미 연결된 행은 `event`만 visit_record.event와
    불일치하는 값으로 설정하는 PATCH를 거부해야 한다 — FK 쌍 불변식은 생성
    시점 가드에 그치지 않으며, 이전까지 CollectionItem.clean()을 호출하는
    곳이 없었다."""
    user = make_user(username="ci-update-fk-pair-conflict")
    visit_event = make_event(title="고정된 방문 이벤트")
    other_event = make_event(title="불일치 이벤트")
    visit_record = make_visit(user, event=visit_event, visited_on="2026-01-01")
    item = create_collection_item(
        user=user, name="FK 쌍 확인", visit_record=visit_record
    )

    with pytest.raises(ValidationError) as exc_info:
        update_collection_item(item=item, event=other_event)

    assert exc_info.value.message_dict == {
        "event": ["visit_record가 설정된 경우 event는 visit_record.event와 일치해야 합니다."]
    }
    item.refresh_from_db()
    assert item.event_id == visit_event.id


@pytest.mark.domain
@pytest.mark.django_db
def test_방문기록이_연결된_아이템의_이벤트를_null로_수정해도_거부된다(
    make_user, make_event, make_visit
):
    """QVL 지적 D1(2026-07-16): 위 FK 쌍 가드는 *병합된* event가 non-null이고
    불일치할 때만 발동했다 — model.clean() 자체 조건이 event_id가 not None임을
    요구해, `PATCH {"event": None}`은 visit_record는 그대로 둔 채 event만
    조용히 분리해 불변식을 누락으로 깼다. quantity 가드는 이미 payload가
    무엇을 건드렸든 병합값(`fields.get("quantity", item.quantity)`)을
    읽는다 — 이 가드도 같은 원칙을 적용해야 한다."""
    user = make_user(username="ci-update-fk-pair-null-event")
    visit_event = make_event(title="고정된 방문 이벤트 2")
    visit_record = make_visit(user, event=visit_event, visited_on="2026-01-01")
    item = create_collection_item(
        user=user, name="FK 쌍 null 확인", visit_record=visit_record
    )

    with pytest.raises(ValidationError):
        update_collection_item(item=item, event=None)

    item.refresh_from_db()
    assert item.event_id == visit_event.id


@pytest.mark.domain
@pytest.mark.django_db
def test_방문기록이_없는_아이템은_이벤트를_자유롭게_수정할_수_있다(
    make_user, make_event
):
    """FK 쌍 가드는 visit_record가 연결된 뒤에만 적용된다 — visit_record가
    없는 행은 event 연결을 자유롭게 바꿀 수 있다."""
    user = make_user(username="ci-update-fk-pair-free")
    new_event = make_event(title="자유롭게 연결할 이벤트")
    item = create_collection_item(user=user, name="자유 편집")

    updated = update_collection_item(item=item, event=new_event)

    assert updated.event_id == new_event.id


@pytest.mark.domain
@pytest.mark.django_db
def test_다른_요청이_먼저_커밋한_뒤에_수정하면_오래된_객체가_아니라_최신_DB_상태_기준으로_거부된다(make_user):
    """보안 게이트 M2(2026-07-16): 실제 스레드 없이 두 PATCH 간 경합을
    재현한다. 호출자 B는 호출자 A의 쓰기가 tradeable_quantity=5를 커밋하기
    전에 `item` 객체를 조회했다 — B의 병합 검사는 B의 오래된 파이썬 객체가
    아니라 행의 *현재* DB 상태(select_for_update 경유)를 기준으로 판단해야
    한다. 그렇지 않으면 B 자신의 병합 검사(quantity=1 vs 오래된
    tradeable_quantity=0)가 통과해버려 결과 UPDATE가 타이밍에 따라 DB
    CheckConstraint를 위반(크래시)하거나 불일치 행을 조용히 커밋한다. 메모리
    인스턴스가 아니라 DB에서 다시 읽어 검증하므로, 잠금 없이 update_fields만
    쓰고 실제로는 영속화하지 않는 save()도 놓치지 않는다."""
    user = make_user(username="ci-update-concurrent-guard")
    item = create_collection_item(
        user=user, name="동시 PATCH 경합", quantity=5, tradeable_quantity=0
    )
    stale_item = CollectionItem.objects.get(pk=item.pk)  # 두 번째 호출자의 조회
    # 다른 요청의 PATCH가 이미 커밋된 상황을 재현한다.
    CollectionItem.objects.filter(pk=item.pk).update(tradeable_quantity=5)

    with pytest.raises(ValidationError):
        update_collection_item(item=stale_item, quantity=1)

    item.refresh_from_db()
    assert item.quantity == 5
    assert item.tradeable_quantity == 5


@pytest.mark.domain
@pytest.mark.django_db
def test_수정_도중_다른_요청이_먼저_삭제하면_DoesNotExist_예외가_발생한다(make_user):
    """보안 게이트 후속(2026-07-16): M2 자체 수정(select_for_update()로
    재조회)이 새로운 TOCTOU 크래시를 만들었다 — 호출자의 원래 조회와 이 호출
    사이에 다른 요청이 행을 삭제하면
    `CollectionItem.objects.select_for_update().get(pk=item.pk)` 자체가
    DoesNotExist를 던진다. 이건 그 지적의 서비스 계층 절반이다 —
    archive/views.py가 이를 Http404로 변환해야 한다(뷰 계층 절반은
    tests/archive/test_collection_items_api.py의
    test_patch_race_with_concurrent_delete_returns_404 참고, 같은 경합
    형태에 대한 VisitRecordPhotoCreateView의 동일한 VisitRecord.DoesNotExist
    -> Http404 가드와 대응)."""
    user = make_user(username="ci-update-concurrent-delete")
    item = create_collection_item(user=user, name="동시 삭제 경합")
    stale_item = CollectionItem.objects.get(pk=item.pk)  # 두 번째 호출자의 조회
    CollectionItem.objects.filter(pk=item.pk).delete()  # 동시 삭제

    with pytest.raises(CollectionItem.DoesNotExist):
        update_collection_item(item=stale_item, quantity=2)
