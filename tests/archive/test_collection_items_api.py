"""CollectionItem API 테스트 — 사용자 소유 굿즈 컬렉션 항목, 본인 소유로만
제한(컬렉션 도메인 설계 계획 §4 PR-C5).

  POST   /api/collection-items/        → 201 (소유자 = request.user, 요청
                                          본문 값은 무시)
  GET    /api/collection-items/        → 페이지네이션 목록(본인 소유, 필터 가능)
  GET    /api/collection-items/<id>/   → 200 또는 404
  PATCH  /api/collection-items/<id>/   → 200 또는 404 (가드가 걸린 수정)
  DELETE /api/collection-items/<id>/   → 204 또는 404
"""
import re
import uuid

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.client import BOUNDARY, MULTIPART_CONTENT, encode_multipart

from archive.models import CollectionItem


# ---------------------------------------------------------------------------
# CP1: 인증 필수
# ---------------------------------------------------------------------------


@pytest.mark.web
@pytest.mark.django_db
def test_미인증_사용자가_컬렉션_목록을_조회하면_인증_오류가_된다(client):
    response = client.get("/api/collection-items/")

    assert response.status_code in (401, 403)


# ---------------------------------------------------------------------------
# CP2: 생성 — 소유자는 요청에서 강제되며 요청 본문 값을 절대 쓰지 않는다
# ---------------------------------------------------------------------------


@pytest.mark.web
@pytest.mark.django_db
def test_다른_사용자_id를_담아_생성해도_소유자는_요청_사용자로_강제된다(client, make_user):
    user = make_user(username="ci-create-owner")
    other = make_user(username="ci-create-payload-user")

    client.force_login(user)
    response = client.post(
        "/api/collection-items/",
        {"user": other.id, "name": "새 굿즈"},
        content_type="application/json",
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "새 굿즈"
    item = CollectionItem.objects.get(id=data["id"])
    assert item.user_id == user.id  # 요청 본문의 "user"는 무시된다


# ---------------------------------------------------------------------------
# CP3: visibility는 쓰기·읽기 모두에서 완전히 제외된다 — 향후 교환 opt-in
# 게이트를 위해 남겨둔 필드로, Stage 4 전까지는 노출하지 않는다(AGENTS.md
# Binding Product Decisions: 교환 노출은 명시적이고 독립 철회 가능한 opt-in이
# 필요하며 아직 승인되지 않음).
# ---------------------------------------------------------------------------


@pytest.mark.web
@pytest.mark.django_db
def test_컬렉션_항목을_생성하면_응답에_정확한_필드_집합이_포함된다(client, make_user):
    user = make_user(username="ci-create-fields")

    client.force_login(user)
    response = client.post(
        "/api/collection-items/",
        {"name": "필드 확인용 굿즈"},
        content_type="application/json",
    )

    assert response.status_code == 201
    assert set(response.json()) == {
        "id",
        "name",
        "work_title",
        "character_name",
        "item_type",
        "quantity",
        "acquired_on",
        "acquisition_source",
        "event",
        "visit_record",
        "image",
        "memo",
        "is_wanted",
        "tradeable_quantity",
        "created_at",
        "updated_at",
    }


# ---------------------------------------------------------------------------
# CP12: create_collection_item의 수량 가드가 던지는 도메인 ValidationError는
# 처리되지 않은 500이 아니라 400으로 나와야 한다 — DRF 기본 예외 처리기는
# django.core.exceptions.ValidationError를 자동으로 변환해주지 않는다.
# ---------------------------------------------------------------------------


@pytest.mark.web
@pytest.mark.django_db
def test_수량이_음수인_컬렉션_항목을_생성하면_400으로_거부된다(client, make_user):
    user = make_user(username="ci-create-negative-quantity")

    client.force_login(user)
    response = client.post(
        "/api/collection-items/",
        {"name": "음수 수량", "quantity": -1},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "quantity" in response.json()
    assert not CollectionItem.objects.filter(name="음수 수량").exists()


# ---------------------------------------------------------------------------
# CP4~CP6: 목록·상세(GET/PATCH/DELETE) 전반에 걸친 소유자 제한
# ---------------------------------------------------------------------------


@pytest.mark.web
@pytest.mark.django_db
def test_컬렉션_목록을_조회하면_본인_소유_항목만_반환된다(client, make_user, make_collection_item):
    user = make_user(username="ci-list-scope")
    other = make_user(username="ci-list-scope-other")
    make_collection_item(user, name="Mine")
    make_collection_item(other, name="Theirs")

    client.force_login(user)
    response = client.get("/api/collection-items/")

    assert response.status_code == 200
    names = [row["name"] for row in response.json()["results"]]
    assert names == ["Mine"]


@pytest.mark.web
@pytest.mark.django_db
def test_타인_소유_컬렉션_항목을_조회하면_404가_된다(
    client, make_user, make_collection_item
):
    owner = make_user(username="ci-detail-get-owner")
    other = make_user(username="ci-detail-get-other")
    item = make_collection_item(owner, name="타인 소유")

    client.force_login(other)
    response = client.get(f"/api/collection-items/{item.id}/")

    assert response.status_code == 404


@pytest.mark.web
@pytest.mark.django_db
def test_타인_소유_컬렉션_항목을_수정하면_404가_되고_원본이_유지된다(
    client, make_user, make_collection_item
):
    owner = make_user(username="ci-detail-patch-owner")
    other = make_user(username="ci-detail-patch-other")
    item = make_collection_item(owner, name="타인 소유 수정 시도")

    client.force_login(other)
    response = client.patch(
        f"/api/collection-items/{item.id}/",
        {"name": "가로채기"},
        content_type="application/json",
    )

    assert response.status_code == 404
    item.refresh_from_db()
    assert item.name == "타인 소유 수정 시도"


@pytest.mark.web
@pytest.mark.django_db
def test_타인_소유_컬렉션_항목을_삭제하면_404가_되고_삭제되지_않는다(
    client, make_user, make_collection_item
):
    owner = make_user(username="ci-detail-delete-owner")
    other = make_user(username="ci-detail-delete-other")
    item = make_collection_item(owner, name="타인 소유 삭제 시도")

    client.force_login(other)
    response = client.delete(f"/api/collection-items/{item.id}/")

    assert response.status_code == 404
    assert CollectionItem.objects.filter(id=item.id).exists()


@pytest.mark.web
@pytest.mark.django_db
def test_소유자가_컬렉션_항목을_삭제하면_204와_함께_삭제된다(client, make_user, make_collection_item):
    user = make_user(username="ci-delete-owner")
    item = make_collection_item(user, name="삭제할 항목")

    client.force_login(user)
    response = client.delete(f"/api/collection-items/{item.id}/")

    assert response.status_code == 204
    assert not CollectionItem.objects.filter(id=item.id).exists()


# ---------------------------------------------------------------------------
# CP13: PATCH는 원시 ModelSerializer 저장이 아니라 가드가 걸린 서비스
# update_collection_item을 거친다.
# ---------------------------------------------------------------------------


@pytest.mark.web
@pytest.mark.django_db
def test_소유자가_컬렉션_항목_필드를_수정하면_변경사항이_저장된다(client, make_user, make_collection_item):
    user = make_user(username="ci-patch-owner")
    item = make_collection_item(user, name="원래 이름")

    client.force_login(user)
    response = client.patch(
        f"/api/collection-items/{item.id}/",
        {"name": "바뀐 이름", "memo": "메모 추가"},
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["name"] == "바뀐 이름"
    item.refresh_from_db()
    assert item.name == "바뀐 이름"
    assert item.memo == "메모 추가"


@pytest.mark.web
@pytest.mark.django_db
def test_미공개_이벤트를_연결해_컬렉션_항목을_생성하면_400으로_거부된다(client, make_user, make_event):
    """`event`는 시리얼라이저에서 Event.objects.published()로 제한된다 —
    VisitRecordSerializer/UserEventStatusSerializer가 이미 쓰는 것과 같은 가드
    (컬렉션 도메인 설계 계획 §4 PR-C5 CP14)."""
    from events.models import Event

    user = make_user(username="ci-create-unpublished-event")
    draft_event = make_event(title="미공개 이벤트", publish_status=Event.PublishStatus.DRAFT)

    client.force_login(user)
    response = client.post(
        "/api/collection-items/",
        {"name": "미공개 이벤트 굿즈", "event": draft_event.id},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "event" in response.json()
    assert not CollectionItem.objects.filter(name="미공개 이벤트 굿즈").exists()


@pytest.mark.web
@pytest.mark.django_db
def test_컬렉션_항목을_미공개_이벤트로_수정하면_400으로_거부되고_기존값이_유지된다(client, make_user, make_event, make_collection_item):
    """CP14는 POST만 다뤘다 — 시리얼라이저의 `event` 필드는 생성·수정이 공유하지만
    PATCH에도 같은 게시 전용 가드가 적용되는지 증명하는 테스트가 없었다."""
    from events.models import Event

    user = make_user(username="ci-patch-unpublished-event")
    draft_event = make_event(title="PATCH 미공개 이벤트", publish_status=Event.PublishStatus.DRAFT)
    item = make_collection_item(user, name="PATCH 대상")

    client.force_login(user)
    response = client.patch(
        f"/api/collection-items/{item.id}/",
        {"event": draft_event.id},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "event" in response.json()
    item.refresh_from_db()
    assert item.event_id is None


@pytest.mark.web
@pytest.mark.django_db
def test_타인의_방문_기록을_연결해_컬렉션_항목을_생성하면_400으로_거부된다(
    client, make_user, make_event, make_visit
):
    """타인의 visit_record는 API 단에서 거부된다 — 시리얼라이저의 소유자 제한
    visit_record 쿼리셋(보안 게이트 M1 강화)이 담당하며, create_collection_item의
    소유권 가드가 심층 방어로 추가된다(컬렉션 도메인 설계 계획 §4 PR-C5 CP15)."""
    user = make_user(username="ci-create-cross-user-visit")
    other = make_user(username="ci-create-cross-user-visit-owner")
    event = make_event(title="타인 방문 이벤트")
    other_visit = make_visit(other, event=event, visited_on="2026-01-01")

    client.force_login(user)
    response = client.post(
        "/api/collection-items/",
        {"name": "타인 방문 굿즈", "visit_record": other_visit.id},
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not CollectionItem.objects.filter(name="타인 방문 굿즈").exists()


def _normalize_pk_in_message(payload):
    """DRF가 PrimaryKeyRelatedField "does not exist" 메시지에 끼워넣는 실제 pk
    값(예: `pk "42"`)을 지워서, 서로 다를 수밖에 없는 id 대신 오류 *형태*로
    두 응답을 비교할 수 있게 한다."""
    return {
        field: [re.sub(r'"\d+"', '"<pk>"', message) for message in messages]
        for field, messages in payload.items()
    }


@pytest.mark.contract
@pytest.mark.django_db
def test_타인_방문_기록과_존재하지_않는_방문_기록은_동일한_오류_형태로_거부되어_존재_여부가_드러나지_않는다(
    client, make_user, make_event, make_visit
):
    """타인의 실제 visit_record id와 존재하지 않는 id는 *같은* 오류 형태로
    실패해야 한다 — 그렇지 않으면 "존재하지만 내 것 아님"과 "존재하지 않음"이
    구분되어, 호출자가 VisitRecord id를 전수 열거할 수 있다(보안 게이트 M1)."""
    user = make_user(username="ci-create-visit-oracle")
    other = make_user(username="ci-create-visit-oracle-owner")
    event = make_event(title="오라클 확인 이벤트")
    other_visit = make_visit(other, event=event, visited_on="2026-01-01")

    client.force_login(user)
    cross_user_response = client.post(
        "/api/collection-items/",
        {"name": "타인 방문 굿즈 오라클", "visit_record": other_visit.id},
        content_type="application/json",
    )
    nonexistent_response = client.post(
        "/api/collection-items/",
        {"name": "존재하지 않는 방문 오라클", "visit_record": other_visit.id + 999999},
        content_type="application/json",
    )

    assert cross_user_response.status_code == 400
    assert nonexistent_response.status_code == 400
    assert _normalize_pk_in_message(cross_user_response.json()) == _normalize_pk_in_message(
        nonexistent_response.json()
    )


@pytest.mark.web
@pytest.mark.django_db
def test_기존_교환_가능_수량보다_적은_수량으로_수정하면_400으로_거부된다(
    client, make_user, make_collection_item
):
    """`quantity`만 보내는 PATCH도 그 행의 기존 `tradeable_quantity`와 비교
    검증돼야 한다 — PATCH가 원시 시리얼라이저 저장이 아니라
    update_collection_item의 병합값 가드를 거친다는 증거(컬렉션 도메인 설계
    계획 §5 인수 기준 3)."""
    user = make_user(username="ci-patch-merge-guard")
    item = make_collection_item(user, name="병합 가드", quantity=5, tradeable_quantity=3)

    client.force_login(user)
    response = client.patch(
        f"/api/collection-items/{item.id}/",
        {"quantity": 1},
        content_type="application/json",
    )

    assert response.status_code == 400
    item.refresh_from_db()
    assert item.quantity == 5


@pytest.mark.web
@pytest.mark.django_db
def test_방문_기록과_충돌하는_이벤트로_수정하면_500이_아닌_400으로_거부된다(
    client, make_user, make_event, make_visit, make_collection_item
):
    """FK 쌍 가드의 거부가 서비스 계층의 `pytest.raises(ValidationError)`
    뿐 아니라 실제 HTTP 400까지 end-to-end로 도달하는지 증명한다 — 실제
    요청으로는 한 번도 검증된 적이 없어 추측이 아니라 여기서 확인한다.

    실측으로 바로잡은 사실: 이 시나리오는 원래
    `_translate_domain_validation_error`의 non-dict `exc.messages` 폴백
    (model.clean()이 평범한 문자열을 던져 NON_FIELD_ERRORS `__all__`로
    나오는 경로)을 검증할 것으로 예상됐지만 실제로는 아니다 — 같은 라운드에
    추가된 D1 수정(병합값 FK 쌍 가드)이 full_clean()/clean()에 도달하기 전에
    이 시나리오를 가로채, 대신 dict 형태의 `ValidationError({"event": ...})`
    를 던진다(응답 본문을 직접 출력해 확인, 추측 아님). D1이 서비스 계층에서
    visit_record/event 조합을 전부 다루게 된 지금, model.clean()의
    NON_FIELD_ERRORS 경로는 API로는 도달 불가능해 보인다 — full_clean()은
    심층 방어로 남지만, `_translate_domain_validation_error`의 이 특정
    분기는 현재 이를 호출하는 경로가 없다(자세한 내용은 작업 로그 참고)."""
    user = make_user(username="ci-patch-fk-pair-http")
    visit_event = make_event(title="HTTP FK 쌍 확인 이벤트")
    other_event = make_event(title="HTTP FK 쌍 불일치 이벤트")
    visit_record = make_visit(user, event=visit_event, visited_on="2026-01-01")
    item = make_collection_item(
        user, name="HTTP FK 쌍 충돌", visit_record=visit_record, event=visit_event
    )

    client.force_login(user)
    response = client.patch(
        f"/api/collection-items/{item.id}/",
        {"event": other_event.id},
        content_type="application/json",
    )

    assert response.status_code == 400
    item.refresh_from_db()
    assert item.event_id == visit_event.id


# ---------------------------------------------------------------------------
# 보안 게이트 후속: update_collection_item 내부의 M2 select_for_update()
# 재조회 자체가, 이 뷰의 get_object()와 그 재조회 사이 창구에서 다른 요청이
# 행을 삭제하면 CollectionItem.DoesNotExist를 던질 수 있다 — M2 수정 자체가
# 만든 새로운 TOCTOU 경합이다. VisitRecordPhotoCreateView는 이미 동일한
# 경합 형태를 VisitRecord.DoesNotExist에 대해 방어하고 있다(archive/views.py).
# ---------------------------------------------------------------------------


@pytest.mark.contract
@pytest.mark.django_db
def test_수정_중_동시에_삭제되면_404가_된다(
    client, make_user, make_collection_item, monkeypatch
):
    """뷰의 get_object()와 update_collection_item의
    select_for_update().get() 재조회 사이에 CollectionItem이 삭제되면, 뷰는
    500이 아니라 404를 반환해야 한다.

    순수 서비스 테스트가 아니라 뷰 계층에 두는 이유: 이 경합은
    archive.views가 임포트한 update_collection_item 참조를 몽키패치해
    시뮬레이션하는데, 그 패치 지점이 여기에만 존재하기 때문이다
    (test_visit_records_api.py의
    test_upload_photo_race_with_concurrent_delete_returns_404 과 동일한
    구조). 이 경합에서 update_collection_item이 실제로
    CollectionItem.DoesNotExist를 던진다는 서비스 계층 사실은
    tests/archive/test_archive_services.py 에서 별도로 다루며, 그 파일은
    archive.services를 직접 임포트할 수 있다.
    """
    user = make_user(username="ci-patch-concurrent-delete")
    item = make_collection_item(user, name="동시 삭제 경합")

    from archive import views as archive_views

    original_update_collection_item = archive_views.update_collection_item

    def racing_update_collection_item(*, item, **fields):
        # 뷰의 get_object()와 서비스의 select_for_update().get() 사이에
        # 동시 삭제가 끼어드는 상황을 시뮬레이션한다.
        CollectionItem.objects.filter(pk=item.pk).delete()
        return original_update_collection_item(item=item, **fields)

    monkeypatch.setattr(
        archive_views, "update_collection_item", racing_update_collection_item
    )

    client.force_login(user)
    response = client.patch(
        f"/api/collection-items/{item.id}/",
        {"name": "실패해야 함"},
        content_type="application/json",
    )

    assert response.status_code == 404
    assert not CollectionItem.objects.filter(pk=item.id).exists()


@pytest.mark.contract
@pytest.mark.django_db
def test_삭제_중_동시_삭제_경합이_발생해도_204로_성공한다(
    client, make_user, make_collection_item, monkeypatch
):
    """추측이 아니라 확인: DELETE도 PATCH와 같은 TOCTOU 경합이 있는가?
    destroy()는 재조회 없이 이미 가져온 객체에 바로 instance.delete()를
    호출하고, Django의 Model.delete()는 행이 이미 없으면 0건 영향(예외 없음)
    이므로 답은 "아니오"여야 한다. Model.delete() 소스만 읽는 대신, 뷰의
    get_object()와 perform_destroy()의 instance.delete() 호출 사이 창구에서
    실제로 행을 삭제해 검증한다."""
    from archive.views import CollectionItemDetailView

    user = make_user(username="ci-delete-concurrent-race")
    item = make_collection_item(user, name="동시 삭제 경합 확인")

    original_get_object = CollectionItemDetailView.get_object

    def racing_get_object(self):
        obj = original_get_object(self)
        # 이 뷰의 소유자 제한 조회와 아래 perform_destroy의
        # instance.delete() 호출 사이에 두 번째 동시 DELETE 요청이 먼저
        # 끝나는 상황을 시뮬레이션한다.
        CollectionItem.objects.filter(pk=obj.pk).delete()
        return obj

    monkeypatch.setattr(CollectionItemDetailView, "get_object", racing_get_object)

    client.force_login(user)
    response = client.delete(f"/api/collection-items/{item.id}/")

    assert response.status_code == 204
    assert not CollectionItem.objects.filter(pk=item.id).exists()


# ---------------------------------------------------------------------------
# CP16~22: 검색/필터 쿼리 파라미터(work_title, character_name, item_type,
# is_wanted, duplicate, tradeable). `duplicate`/`tradeable`은 저장 필드가
# 아니라 quantity/tradeable_quantity에서 *파생*된다 — 계획서가 별도의
# duplicate_count 컬럼을 의도적으로 없앴다(§3-1).
# ---------------------------------------------------------------------------


@pytest.mark.web
@pytest.mark.django_db
def test_작품명으로_컬렉션_목록을_필터링하면_일치하는_항목만_반환된다(client, make_user, make_collection_item):
    user = make_user(username="ci-filter-work-title")
    make_collection_item(user, name="일치", work_title="작품 A")
    make_collection_item(user, name="불일치", work_title="작품 B")

    client.force_login(user)
    response = client.get("/api/collection-items/?work_title=작품 A")

    assert response.status_code == 200
    names = [row["name"] for row in response.json()["results"]]
    assert names == ["일치"]


@pytest.mark.web
@pytest.mark.django_db
def test_캐릭터명으로_컬렉션_목록을_필터링하면_일치하는_항목만_반환된다(client, make_user, make_collection_item):
    user = make_user(username="ci-filter-character")
    make_collection_item(user, name="일치", character_name="캐릭터 A")
    make_collection_item(user, name="불일치", character_name="캐릭터 B")

    client.force_login(user)
    response = client.get("/api/collection-items/?character_name=캐릭터 A")

    assert response.status_code == 200
    names = [row["name"] for row in response.json()["results"]]
    assert names == ["일치"]


@pytest.mark.web
@pytest.mark.django_db
def test_굿즈_유형으로_컬렉션_목록을_필터링하면_일치하는_항목만_반환된다(client, make_user, make_collection_item):
    user = make_user(username="ci-filter-item-type")
    make_collection_item(user, name="일치", item_type="keyring")
    make_collection_item(user, name="불일치", item_type="badge")

    client.force_login(user)
    response = client.get("/api/collection-items/?item_type=keyring")

    assert response.status_code == 200
    names = [row["name"] for row in response.json()["results"]]
    assert names == ["일치"]


@pytest.mark.web
@pytest.mark.django_db
def test_구함_여부로_컬렉션_목록을_필터링하면_일치하는_항목만_반환된다(client, make_user, make_collection_item):
    user = make_user(username="ci-filter-wanted")
    make_collection_item(user, name="구함", is_wanted=True)
    make_collection_item(user, name="보유", is_wanted=False)

    client.force_login(user)
    response = client.get("/api/collection-items/?is_wanted=true")

    assert response.status_code == 200
    names = [row["name"] for row in response.json()["results"]]
    assert names == ["구함"]


@pytest.mark.web
@pytest.mark.django_db
def test_구함_필터를_false로_보내면_API에서는_리다이렉트_없이_보유_항목만_반환된다(
    client, make_user, make_collection_item
):
    """DRF API 경계 고정(사용자 결정): 웹 페이지의 /collection/?is_wanted=false
    는 예전 북마크 호환을 위해 ?owned=true로 302 리다이렉트하지만(보유하며
    구함인 행이 그 URL에서 잘못 제외되던 문제 때문), API는 자체 버저닝
    계약을 가진 안정적인 머신 인터페이스라 리다이렉트하면 안 되고 is_wanted는
    원래 의미(수량과 무관하게 is_wanted가 False)를 유지한다. quantity>0 &
    is_wanted=True인 행은 "보유" 상태여도 여전히 제외돼야 하며, 이는 이
    엔드포인트가 웹 리다이렉트의 영향을 받지 않았음을 증명한다."""
    user = make_user(username="ci-filter-not-wanted")
    make_collection_item(user, name="보유", quantity=3, is_wanted=False)
    make_collection_item(user, name="보유하며구함", quantity=2, is_wanted=True)

    client.force_login(user)
    response = client.get("/api/collection-items/?is_wanted=false")

    assert response.status_code == 200
    names = [row["name"] for row in response.json()["results"]]
    assert names == ["보유"]


@pytest.mark.web
@pytest.mark.django_db
def test_중복_필터는_수량에서_파생되어_저장된_필드_없이_동작한다(
    client, make_user, make_collection_item
):
    """`duplicate`는 저장 필드가 없다 — 별도 duplicate_count 컬럼이 아니라
    quantity >= 2 여야 한다(컬렉션 도메인 설계 계획 §3-1)."""
    user = make_user(username="ci-filter-duplicate")
    make_collection_item(user, name="중복", quantity=2)
    make_collection_item(user, name="단일", quantity=1)

    client.force_login(user)
    response = client.get("/api/collection-items/?duplicate=true")

    assert response.status_code == 200
    names = [row["name"] for row in response.json()["results"]]
    assert names == ["중복"]
    assert "duplicate_count" not in response.json()["results"][0]


@pytest.mark.web
@pytest.mark.django_db
def test_교환가능_필터는_교환_가능_수량에서_파생되어_동작한다(
    client, make_user, make_collection_item
):
    """`tradeable`은 별도 플래그 필드가 없다 — tradeable_quantity > 0 이어야
    한다(컬렉션 도메인 설계 계획 §3-1)."""
    user = make_user(username="ci-filter-tradeable")
    make_collection_item(user, name="교환 가능", quantity=3, tradeable_quantity=1)
    make_collection_item(user, name="교환 불가", quantity=3, tradeable_quantity=0)

    client.force_login(user)
    response = client.get("/api/collection-items/?tradeable=true")

    assert response.status_code == 200
    names = [row["name"] for row in response.json()["results"]]
    assert names == ["교환 가능"]


@pytest.mark.web
@pytest.mark.django_db
def test_보유_필터는_수량에서_파생되어_저장된_필드_없이_동작한다(
    client, make_user, make_collection_item
):
    """`owned`는 저장 필드가 없다 — 별도 owned 플래그 컬럼이 아니라
    quantity > 0 이어야 한다(컬렉션 도메인 설계 계획 §3-1)."""
    user = make_user(username="ci-filter-owned")
    make_collection_item(user, name="가진 것", quantity=3)
    make_collection_item(user, name="안 가진 것", quantity=0)

    client.force_login(user)
    response = client.get("/api/collection-items/?owned=true")

    assert response.status_code == 200
    names = [row["name"] for row in response.json()["results"]]
    assert names == ["가진 것"]


@pytest.mark.web
@pytest.mark.django_db
def test_보유_필터에_잘못된_값을_보내면_400으로_거부된다(client, make_user):
    user = make_user(username="ci-filter-owned-invalid")

    client.force_login(user)
    response = client.get("/api/collection-items/?owned=maybe")

    assert response.status_code == 400


@pytest.mark.web
@pytest.mark.django_db
def test_구함_필터에_잘못된_값을_보내면_400으로_거부된다(client, make_user):
    """CollectionItemQuerySerializer가 쿼리 파라미터를
    list_user_collection_items에 도달하기 전에 검증한다
    (UserEventStatusQuerySerializer와 동일한 구조 — 컬렉션 도메인 설계 계획
    §4 PR-C5 CP22)."""
    user = make_user(username="ci-filter-invalid")

    client.force_login(user)
    response = client.get("/api/collection-items/?is_wanted=maybe")

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# L4(보안 게이트) — 텍스트 필터 파라미터는 모델 자체의 max_length를 넘는 값을
# 거부해야 한다(밑바탕 CharField 제한과 일치).
# ---------------------------------------------------------------------------


@pytest.mark.web
@pytest.mark.django_db
def test_작품명_필터가_최대_길이를_초과하면_400으로_거부된다(client, make_user):
    user = make_user(username="ci-filter-work-title-too-long")

    client.force_login(user)
    response = client.get("/api/collection-items/?work_title=" + "가" * 256)

    assert response.status_code == 400


@pytest.mark.web
@pytest.mark.django_db
def test_캐릭터명_필터가_최대_길이를_초과하면_400으로_거부된다(
    client, make_user
):
    user = make_user(username="ci-filter-character-name-too-long")

    client.force_login(user)
    response = client.get("/api/collection-items/?character_name=" + "가" * 256)

    assert response.status_code == 400


@pytest.mark.web
@pytest.mark.django_db
def test_굿즈_유형_필터가_최대_길이를_초과하면_400으로_거부된다(client, make_user):
    user = make_user(username="ci-filter-item-type-too-long")

    client.force_login(user)
    response = client.get("/api/collection-items/?item_type=" + "가" * 101)

    assert response.status_code == 400


# ---------------------------------------------------------------------------
# 도메인 게이트 M1 — *빈* 필터 값(`?<param>=`)은 파라미터가 아예 없는 것과
# 똑같이 "이 조건으로 필터링하지 않음"을 뜻해야 한다. 여섯 필터 모두 이
# 빈값 계약을 공유해서, 클라이언트(C5b의 필터 폼)가 필드별 공백 제거 없이
# 폼을 그대로 직렬화할 수 있게 한다. 진짜 잘못된 값(예: `?is_wanted=ture`)은
# 여전히 400이어야 한다 — 허용하는 건 빈값뿐이지 오타가 아니다.
# ---------------------------------------------------------------------------


@pytest.mark.web
@pytest.mark.django_db
@pytest.mark.parametrize(
    "query_param",
    ["work_title", "character_name", "item_type", "is_wanted", "duplicate", "tradeable", "owned"],
    ids=["작품명", "캐릭터명", "굿즈_유형", "구함_여부", "중복", "교환가능", "보유_여부"],
)
def test_빈_필터값을_보내면_필터가_적용되지_않은_것과_동일하게_처리된다(
    client, make_user, make_collection_item, query_param
):
    user = make_user(username=f"ci-filter-empty-{query_param}")
    make_collection_item(user, name="항목 1")
    make_collection_item(user, name="항목 2")

    client.force_login(user)
    response = client.get(f"/api/collection-items/?{query_param}=")

    assert response.status_code == 200
    assert response.json()["count"] == 2
# CP23~24c: 이미지 업로드 — 방문 사진/직접 등록 항목과 동일한 검증 파이프라인
# (events.image_validation.validate_uploaded_image)을 공유한다.
# ---------------------------------------------------------------------------


@pytest.mark.web
@pytest.mark.django_db
def test_이미지가_아닌_바이트를_jpg로_위장해_업로드하면_400으로_거부된다(client, make_user, settings, tmp_path):
    """.jpg로 위장한 가짜 바이트는 Pillow의 내용 검사로 거부돼야 한다."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user(username="ci-img-fake")

    client.force_login(user)
    response = client.post(
        "/api/collection-items/",
        {
            "name": "스푸핑 이미지",
            "image": SimpleUploadedFile(
                "not_an_image.jpg", b"notanimage", content_type="image/jpeg"
            ),
        },
    )

    assert response.status_code == 400
    assert "image" in response.json()
    assert not CollectionItem.objects.filter(name="스푸핑 이미지").exists()


@pytest.mark.web
@pytest.mark.django_db
def test_5MB를_초과하는_이미지를_업로드하면_400으로_거부된다(
    client, make_user, png_bytes, settings, tmp_path
):
    """5MB를 넘는 이미지는 400으로 거부돼야 한다(압축 폭탄 방어)."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user(username="ci-img-big")

    big_png = png_bytes()
    big_content = big_png + b"\x00" * (5 * 1024 * 1024 + 1 - len(big_png))

    client.force_login(user)
    response = client.post(
        "/api/collection-items/",
        {
            "name": "초대형 이미지",
            "image": SimpleUploadedFile("big.png", big_content, content_type="image/png"),
        },
    )

    assert response.status_code == 400
    assert "image" in response.json()


@pytest.mark.web
@pytest.mark.django_db
def test_SVG_파일을_업로드하면_400으로_거부된다(client, make_user, settings, tmp_path):
    """Pillow가 받아들일 수 있어도 SVG 파일은 거부돼야 한다."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user(username="ci-img-svg")
    svg_content = b"<svg xmlns='http://www.w3.org/2000/svg'><circle r='5'/></svg>"

    client.force_login(user)
    response = client.post(
        "/api/collection-items/",
        {
            "name": "SVG 업로드",
            "image": SimpleUploadedFile("icon.svg", svg_content, content_type="image/svg+xml"),
        },
    )

    assert response.status_code == 400
    assert "image" in response.json()


@pytest.mark.web
@pytest.mark.django_db
def test_이미지를_교체하면_기존_파일이_삭제된다(
    client,
    make_user,
    make_collection_item,
    png_bytes,
    settings,
    tmp_path,
    django_capture_on_commit_callbacks,
):
    """보안 게이트 M3: CollectionItem에 새 이미지를 PATCH하면 교체되는 기존
    파일을 삭제해야 한다 — Django FileField 재할당만으로는 예전 저장 객체가
    지워지지 않고, post_delete는 행 삭제 시에만 발생하며 제자리 수정에는
    발생하지 않는다. 이걸 하지 않으면 같은 항목에 이미지 PATCH를 반복할
    때마다 사용자별로 고아 파일이 무한히 쌓인다. CollectionItem은 이미지와
    수정 경로를 모두 가진 첫 archive 모델이라(PersonalEntry는 PATCH가 없고
    VisitRecordPhoto는 생성/삭제만 가능) 이번 C5에서 새로 생긴 지점이다."""
    settings.MEDIA_ROOT = str(tmp_path)
    user = make_user(username="ci-patch-image-replace")
    item = make_collection_item(user, name="이미지 교체")

    client.force_login(user)
    # Django 테스트 클라이언트는 .post()에서만 멀티파트 파일 업로드를 자동
    # 인코딩한다 — .patch()는 `data`를 인코딩 없이 그대로 넘기므로, 파일
    # 업로드는 여기서 직접 멀티파트로 인코딩해야 한다(encode_multipart/BOUNDARY).
    with django_capture_on_commit_callbacks(execute=True):
        first_response = client.patch(
            f"/api/collection-items/{item.id}/",
            encode_multipart(
                BOUNDARY,
                {"image": SimpleUploadedFile("first.png", png_bytes(), content_type="image/png")},
            ),
            content_type=MULTIPART_CONTENT,
        )
    assert first_response.status_code == 200
    item.refresh_from_db()
    storage = item.image.storage
    first_file_name = item.image.name
    assert storage.exists(first_file_name)

    with django_capture_on_commit_callbacks(execute=True):
        second_response = client.patch(
            f"/api/collection-items/{item.id}/",
            encode_multipart(
                BOUNDARY,
                {
                    "image": SimpleUploadedFile(
                        "second.png", png_bytes(color=(0, 255, 0)), content_type="image/png"
                    )
                },
            ),
            content_type=MULTIPART_CONTENT,
        )
    assert second_response.status_code == 200
    item.refresh_from_db()
    second_file_name = item.image.name

    assert second_file_name != first_file_name
    assert not storage.exists(first_file_name)
    assert storage.exists(second_file_name)


# ---------------------------------------------------------------------------
# INTG-BE-01-CI-WEB (bfcache 중복 생성 계획 §6) — client_token 멱등성의 HTTP
# 경계 계약: 시리얼라이저가 쓰기 전용 client_token을
# create_collection_item의 validated_data까지 실제로 전달해야 하고, 그
# 필드가 응답에 절대 다시 노출되면 안 된다. 도메인 계층의 재전송 처리는
# tests/archive/test_archive_services.py 에서 이미 증명됐고, 여기서는 그
# 위의 DRF 연결을 증명한다.
# ---------------------------------------------------------------------------


@pytest.mark.web
@pytest.mark.django_db
def test_같은_클라이언트_토큰으로_컬렉션_항목_생성_POST를_두_번_보내면_두_응답_모두_201이고_동일한_id를_반환하며_DB에는_행이_하나만_생성된다(
    client, make_user
):
    user = make_user(username="ci-create-client-token-idempotent")
    client_token = str(uuid.uuid4())

    client.force_login(user)
    first_response = client.post(
        "/api/collection-items/",
        {"name": "멱등 생성 굿즈", "client_token": client_token},
        content_type="application/json",
    )
    second_response = client.post(
        "/api/collection-items/",
        {"name": "멱등 생성 굿즈", "client_token": client_token},
        content_type="application/json",
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert first_response.json()["id"] == second_response.json()["id"]
    assert "client_token" not in first_response.json()
    assert "client_token" not in second_response.json()
    assert CollectionItem.objects.count() == 1


# ---------------------------------------------------------------------------
# INTG-BE-07 (bfcache 중복 생성 계획 §6, DAR 필수 수정 ③) —
# CollectionItemSerializer는 생성·수정이 공유한다. PATCH로 보낸
# client_token이 기존 토큰을 덮어쓰면 안 된다 — 그러면 생성 시점의 멱등
# 키가 수정 경로로 새어나간다.
# ---------------------------------------------------------------------------


@pytest.mark.web
@pytest.mark.django_db
def test_컬렉션_항목_PATCH_요청에_클라이언트_토큰을_담아_보내도_기존_토큰_값은_변경되지_않는다(
    client, make_user
):
    user = make_user(username="ci-patch-client-token-pinned")
    original_token = uuid.uuid4()

    client.force_login(user)
    create_response = client.post(
        "/api/collection-items/",
        {"name": "토큰 고정 확인", "client_token": str(original_token)},
        content_type="application/json",
    )
    assert create_response.status_code == 201
    item_id = create_response.json()["id"]

    response = client.patch(
        f"/api/collection-items/{item_id}/",
        {"name": "이름 변경", "client_token": str(uuid.uuid4())},
        content_type="application/json",
    )

    assert response.status_code == 200
    item = CollectionItem.objects.get(id=item_id)
    assert item.client_token == original_token


# ---------------------------------------------------------------------------
# INTG-BE-05-CI (bfcache 중복 생성 계획 §6, 검증 경계 "web/slow") — 생성
# 엔드포인트는 위의 client_token 멱등 가드와는 별개로 무차별 반복 POST도
# 막아야 한다: 분당 30건의 스로틀이 CollectionItem 생성을 제한하며,
# tests/archive/test_promotion_api.py의 일일 승격 플러드 테스트
# (test_일일_승격_한도를_초과하면_429로_제한된다)와 같은 구조다. GET(목록)
# 은 영향을 받으면 안 된다 — 스로틀은 쓰기 경로만 지킨다.
# ---------------------------------------------------------------------------


@pytest.mark.web
@pytest.mark.slow
@pytest.mark.django_db
def test_컬렉션_항목_생성_요청이_설정된_한도를_초과하면_429로_제한된다(client, make_user):
    user = make_user(username="ci-create-flood")
    client.force_login(user)

    # 분당 30건 한도: 30번은 성공하고 31번째부터 스로틀에 걸린다.
    for i in range(30):
        response = client.post(
            "/api/collection-items/",
            {"name": f"한도 확인 굿즈 {i}"},
            content_type="application/json",
        )
        assert response.status_code == 201, f"create {i} should succeed"

    throttled = client.post(
        "/api/collection-items/",
        {"name": "한도 초과 굿즈"},
        content_type="application/json",
    )

    assert throttled.status_code == 429
    assert CollectionItem.objects.count() == 30

    listed = client.get("/api/collection-items/")
    assert listed.status_code == 200
