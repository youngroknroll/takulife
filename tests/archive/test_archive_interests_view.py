"""archive_interests page view — SSR rendering, not the JSON API
(moved from tests/archive/test_event_interest_api.py).

Phase V additions below observe HTTP behavior only (status code, template
context, response body) — no archive.queries/archive.services import, per
tests/core/test_architecture_boundaries.py's view-test boundary guard.
"""
from datetime import timedelta

import pytest
from django.utils import timezone

pytestmark = pytest.mark.web

# Anchored to the real "today" (django.utils.timezone.localdate()) — the
# same function core.views.archive_interests uses internally when it is not
# given an explicit `today`. A hardcoded calendar date drifts out of sync
# with derive_event_display's status/dday thresholds (events/presenters.py)
# as soon as the suite runs on a different day, flipping intended
# ongoing/upcoming fixtures to "ended" (dday=None) and breaking the row
# assertions below.
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
    """V1: ?q= is wired through to the rendered rows — a non-matching 찜
    must not appear once a search term is active."""
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
    """V2: an unrecognised ?sort= must not 500 (guards against a bare label
    dict lookup by an unvalidated slug) and falls back to the default sort."""
    user = make_user(username="interests-v2-user")

    client.force_login(user)
    response = client.get("/archive/interests/", {"sort": "존재하지-않는-정렬"})

    assert response.status_code == 200
    assert response.context["selected_sort"] == ""


@pytest.mark.django_db
def test_페이저_쿼리에_검색어와_정렬값이_모두_보존된다(client, make_user, make_event, make_interest):
    """V3: pager_query keeps both q and sort in its query-string tail."""
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
    """V4: pagination actually slices the list (ARCHIVE_INTEREST_PAGE_SIZE=10,
    §1 D4) — 11 rows split into a 10-row page 1 and a 1-row page 2."""
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
    """V5: the ongoing/planned-overlap summary counts are unaffected by an
    active ?q= — they always describe the user's full 찜 set, mirroring the
    sibling tabs' summary-card behavior."""
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
    """V6: an official (event-linked) 찜 row carries a non-null status/dday
    pair (events.presenters.derive_event_display)."""
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
    """V7: an official row reflects the viewer's own user_status — §1 D1's
    can_plan = is_official and user_status == "" depends on this being wired
    through so a shared "방문 예정" button never appears on a row the user
    has already marked 방문 완료/기타 상태."""
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
    """V8: an unofficial (personal_entry-linked) 찜 row has no status/dday —
    it has no run period, unlike an official event."""
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
    """V9: another user's 찜 rows and summary counts never leak into the
    viewer's own page."""
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
    """V10: an ended official row must not offer 방문 예정 추가 — the button
    lets a viewer create a UserEventStatus on an event that has already
    finished, which is meaningless (matches the design's ended-row
    treatment). can_plan must be False even though user_status is still ""
    (no status recorded yet)."""
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
    """V11: contrast case for V10 — an ongoing or upcoming official row with
    no recorded user_status still offers 방문 예정 추가 (can_plan stays True;
    only the ended-row exclusion added for V10 should change behavior)."""
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
