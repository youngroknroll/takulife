"""archive_interests 페이지 뷰(SSR 렌더링, JSON API 아님) 테스트
(tests/archive/test_event_interest_api.py에서 이동).

아래 Phase V 추가분은 HTTP 동작(상태 코드, 템플릿 컨텍스트, 응답 본문)만
관찰한다 — tests/core/test_architecture_boundaries.py의 뷰 테스트 경계
가드에 따라 archive.queries/archive.services를 임포트하지 않는다.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

pytestmark = pytest.mark.web

# 실제 "오늘"(django.utils.timezone.localdate())에 고정한다 — core.views.
# archive_interests가 명시적 today 없이 내부에서 쓰는 함수와 동일하다.
# 날짜를 하드코딩하면 테스트가 다른 날 실행될 때 derive_event_display의
# 상태/디데이 기준(events/presenters.py)과 어긋나 진행중/예정 픽스처가
# "종료"(dday=None)로 뒤집히며 아래 행 단언이 깨진다.
TODAY = timezone.localdate()


@pytest.mark.django_db
def test_사용자가_관심_등록한_행사는_아카이브_관심_목록_페이지에_표시된다(client, make_user, make_event, make_interest):
    user = make_user(username="interests-page-user")
    event = make_event(title="Page Event")
    make_interest(user, event=event)

    client.force_login(user)
    response = client.get("/archive/interests/")

    assert response.status_code == 200
    assert str(event.id).encode() in response.content


@pytest.mark.django_db
def test_비로그인_사용자가_아카이브_관심_목록_페이지에_접근하면_로그인_페이지로_리다이렉트된다(client):
    response = client.get("/archive/interests/")
    assert response.status_code == 302
    assert "/accounts/login/" in response["Location"]


# ---------------------------------------------------------------------------
# Phase V — 찜 목록 페이지 검색/정렬/페이지네이션/통계 배선 (찜 브리프 §3)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_검색어_파라미터가_찜_목록_결과를_좁힌다(client, make_user, make_event, make_interest):
    """V1: ?q= 가 렌더된 행까지 배선된다 — 검색어가 활성화되면 불일치하는
    찜은 나타나면 안 된다."""
    user = make_user(username="interests-v1-user")
    matched = make_event(title="라이브_검색_대상_행사")
    unmatched = make_event(title="다른_행사_제목")
    make_interest(user, event=matched)
    make_interest(user, event=unmatched)

    client.force_login(user)
    response = client.get("/archive/interests/", {"q": "라이브_검색_대상"})

    assert response.status_code == 200
    assert matched.title.encode() in response.content
    assert unmatched.title.encode() not in response.content


@pytest.mark.django_db
def test_알수없는_정렬값도_200을_반환하고_기본_정렬로_폴백한다(client, make_user):
    """V2: 인식할 수 없는 ?sort= 는 500이 아니라 기본 정렬로 폴백해야 한다
    (검증되지 않은 슬러그로 라벨 딕셔너리를 바로 조회하는 사고를 막는다)."""
    user = make_user(username="interests-v2-user")

    client.force_login(user)
    response = client.get("/archive/interests/", {"sort": "존재하지-않는-정렬"})

    assert response.status_code == 200
    assert response.context["selected_sort"] == ""


@pytest.mark.django_db
def test_페이저_쿼리에_검색어와_정렬값이_모두_보존된다(client, make_user, make_event, make_interest):
    """V3: pager_query는 쿼리스트링 꼬리에 q와 sort를 모두 유지한다."""
    user = make_user(username="interests-v3-user")
    event = make_event(title="페이저_보존_행사")
    make_interest(user, event=event)

    client.force_login(user)
    response = client.get("/archive/interests/", {"q": "페이저_보존", "sort": "oldest"})

    assert response.status_code == 200
    pager_query = response.context["pager_query"]
    assert "q=" in pager_query
    assert "sort=oldest" in pager_query


@pytest.mark.django_db
def test_페이지네이션이_찜_목록을_실제로_자른다(client, make_user, make_event, make_interest):
    """V4: 페이지네이션이 실제로 목록을 자른다(ARCHIVE_INTEREST_PAGE_SIZE=10,
    §1 D4) — 11행이 1페이지 10행 + 2페이지 1행으로 나뉜다."""
    user = make_user(username="interests-v4-user")
    for i in range(11):
        event = make_event(title=f"페이지네이션 행사 {i:02d}")
        make_interest(user, event=event)

    client.force_login(user)
    page_one = client.get("/archive/interests/")
    page_two = client.get("/archive/interests/", {"page": "2"})

    assert page_one.status_code == 200
    assert page_two.status_code == 200
    assert len(page_one.context["page_obj"].object_list) == 10
    assert len(page_two.context["page_obj"].object_list) == 1


@pytest.mark.django_db
def test_요약_통계_3종은_검색어_유무와_무관하게_동일하다(
    client, make_user, make_event, make_interest, make_status
):
    """V5: 진행중/예정중복 요약 집계는 활성 ?q= 의 영향을 받지 않는다 —
    형제 탭 요약 카드와 마찬가지로 항상 사용자 전체 찜 집합을 나타낸다."""
    user = make_user(username="interests-v5-user")
    ongoing = make_event(
        title="V5_진행중_행사", start_date=TODAY, end_date=TODAY + timedelta(days=10)
    )
    planned = make_event(
        title="V5_방문예정_행사",
        start_date=TODAY + timedelta(days=5),
        end_date=TODAY + timedelta(days=6),
    )
    make_interest(user, event=ongoing)
    make_interest(user, event=planned)
    make_status(user, event=planned, status="planned")

    client.force_login(user)
    without_q = client.get("/archive/interests/")
    with_q = client.get("/archive/interests/", {"q": "이_검색어는_아무것도_매칭하지_않는다"})

    assert without_q.context["ongoing_count"] == with_q.context["ongoing_count"]
    assert (
        without_q.context["planned_overlap_count"]
        == with_q.context["planned_overlap_count"]
    )


@pytest.mark.django_db
def test_공식_찜_행에는_상태와_디데이가_붙는다(client, make_user, make_event, make_interest):
    """V6: 공식(이벤트 연결) 찜 행은 null이 아닌 status/dday 쌍을 담는다
    (events.presenters.derive_event_display)."""
    user = make_user(username="interests-v6-user")
    event = make_event(
        title="V6_공식_행사", start_date=TODAY, end_date=TODAY + timedelta(days=10)
    )
    make_interest(user, event=event)

    client.force_login(user)
    response = client.get("/archive/interests/")

    row = response.context["interest_rows"][0]
    assert row["status"] is not None
    assert row["dday"] is not None


@pytest.mark.django_db
def test_공식_찜_행에는_본인의_방문_상태가_반영된다(
    client, make_user, make_event, make_interest, make_status
):
    """V7: 공식 행은 조회자 본인의 user_status를 반영한다 — §1 D1의
    can_plan = is_official and user_status == "" 규칙이 이 배선에 의존하며,
    이미 방문 완료/기타 상태로 표시한 행에는 "방문 예정" 버튼이 나오면
    안 된다."""
    user = make_user(username="interests-v7-user")
    event = make_event(
        title="V7_공식_행사", start_date=TODAY, end_date=TODAY + timedelta(days=10)
    )
    make_interest(user, event=event)
    make_status(user, event=event, status="visited")

    client.force_login(user)
    response = client.get("/archive/interests/")

    row = response.context["interest_rows"][0]
    assert row["user_status"] == "visited"
    assert row["can_plan"] is False


@pytest.mark.django_db
def test_비공식_찜_행에는_상태와_디데이가_없다(client, make_user, make_entry, make_interest):
    """V8: 비공식(personal_entry 연결) 찜 행은 status/dday가 없다 — 공식
    이벤트와 달리 운영 기간이 없기 때문이다."""
    user = make_user(username="interests-v8-user")
    place = make_entry(user, title="V8 개인 장소")
    make_interest(user, personal_entry=place)

    client.force_login(user)
    response = client.get("/archive/interests/")

    row = response.context["interest_rows"][0]
    assert row["status"] is None
    assert row["dday"] is None


@pytest.mark.django_db
def test_타인의_찜과_통계는_화면에_노출되지_않는다(
    client, make_user, make_event, make_interest, make_status
):
    """V9: 타인의 찜 행과 요약 집계는 조회자 본인 페이지에 절대 노출되면
    안 된다."""
    user = make_user(username="interests-v9-user")
    other = make_user(username="interests-v9-other")
    other_event = make_event(
        title="V9_타인_행사", start_date=TODAY, end_date=TODAY + timedelta(days=10)
    )
    make_interest(other, event=other_event)
    make_status(other, event=other_event, status="planned")

    client.force_login(user)
    response = client.get("/archive/interests/")

    assert other_event.title.encode() not in response.content
    assert response.context["ongoing_count"] == 0
    assert response.context["planned_overlap_count"] == 0


@pytest.mark.django_db
def test_종료된_공식_찜_행은_방문_예정_추가_버튼을_제공하지_않는다(
    client, make_user, make_event, make_interest
):
    """V10: 종료된 공식 행은 방문 예정 추가를 제공하면 안 된다 — 이 버튼은
    이미 끝난 이벤트에 UserEventStatus를 만들게 하는데, 이는 의미가 없다
    (디자인의 종료 행 처리와 일치). user_status가 아직 ""(기록 없음)여도
    can_plan은 False여야 한다."""
    user = make_user(username="interests-v10-user")
    ended = make_event(
        title="V10_종료된_행사",
        start_date=TODAY - timedelta(days=10),
        end_date=TODAY - timedelta(days=1),
    )
    make_interest(user, event=ended)

    client.force_login(user)
    response = client.get("/archive/interests/")

    row = response.context["interest_rows"][0]
    assert row["status"] == "ended"
    assert row["user_status"] == ""
    assert row["can_plan"] is False


@pytest.mark.django_db
def test_진행중이거나_예정인_공식_찜_행은_상태가_없으면_방문_예정_추가_버튼을_제공한다(
    client, make_user, make_event, make_interest
):
    """V11: V10의 대조 사례 — 진행중이거나 예정인 공식 행은 user_status
    기록이 없어도 방문 예정 추가를 여전히 제공한다(can_plan은 True 유지;
    V10에서 추가된 종료 행 제외만 동작을 바꿔야 한다)."""
    user = make_user(username="interests-v11-user")
    ongoing = make_event(
        title="V11_진행중_행사", start_date=TODAY, end_date=TODAY + timedelta(days=10)
    )
    upcoming = make_event(
        title="V11_예정_행사",
        start_date=TODAY + timedelta(days=5),
        end_date=TODAY + timedelta(days=6),
    )
    make_interest(user, event=ongoing)
    make_interest(user, event=upcoming)

    client.force_login(user)
    response = client.get("/archive/interests/")

    rows_by_event = {row["subject"]["title"]: row for row in response.context["interest_rows"]}
    assert rows_by_event["V11_진행중_행사"]["status"] == "ongoing"
    assert rows_by_event["V11_진행중_행사"]["can_plan"] is True
    assert rows_by_event["V11_예정_행사"]["status"] == "upcoming"
    assert rows_by_event["V11_예정_행사"]["can_plan"] is True
