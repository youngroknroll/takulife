"""Phase 3 UI: 아카이브 목록 페이지(기록장/예정 목록/찜 목록)는 공식 Event 행과
비공식 PersonalEntry 행을 null-safe하게 함께 렌더링하며 비공식 행을 표시한다.
개인 행에서 순진하게 ``row.event.*``에 접근하면 나는 AttributeError를 막는
뷰 레벨 가드를 검증한다.
"""
import pytest

pytestmark = pytest.mark.web


@pytest.fixture
def mixed_user(make_user, make_event, make_entry, make_status, make_interest):
    """공식·비공식 상태와 찜을 모두 보유한 사용자."""
    user = make_user(username="mixed")
    event = make_event(title="공식 팝업", location_name="서울 성수")
    entry = make_entry(user, kind="goods", title="투명 아크릴", category="굿즈")
    make_status(user, event=event, status="planned")
    make_status(user, personal_entry=entry, status="planned")
    make_interest(user, event=event)
    make_interest(user, personal_entry=entry)
    return user, event, entry


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url", ["/archive/", "/archive/statuses/"], ids=["전체_보기", "나의_일정"]
)
def test_기록장_페이지에_공식_행사와_비공식_항목이_함께_렌더링된다(client, mixed_user, url):
    user, event, entry = mixed_user
    client.force_login(user)

    response = client.get(url)

    assert response.status_code == 200
    body = response.content.decode()
    assert event.title in body
    assert entry.title in body
    assert "직접 등록" in body


@pytest.mark.django_db
def test_찜_목록_페이지에_공식_행사와_비공식_항목이_함께_렌더링된다(client, mixed_user):
    user, event, entry = mixed_user
    client.force_login(user)

    response = client.get("/archive/interests/")

    assert response.status_code == 200
    body = response.content.decode()
    assert event.title in body
    assert entry.title in body
    assert "직접 등록" in body


@pytest.mark.django_db
def test_비공식_항목의_예정_행은_공개_행사_상세_링크를_갖지_않는다(client, make_user, make_entry, make_status):
    """비공개 개인 항목은 공개 /events/ 페이지로 링크되면 안 된다."""
    user = make_user(username="no-leak-link")
    entry = make_entry(user, kind="place", title="비공식 카페")
    status = make_status(user, personal_entry=entry, status="planned")
    client.force_login(user)

    response = client.get("/archive/statuses/")

    assert response.status_code == 200
    body = response.content.decode()
    # 존재하는 상세 링크는 행사 기반뿐이어야 하며, 이 개인 행은
    # /events/<id>/ 링크를 만들지 않는다.
    assert f"/events/{status.id}/" not in body
