"""Tests for server-side q-search across the four archive list pages.

Behavior under test:
- ?q=<term> filters each archive list server-side.
- q matches event.title and event.location_name via UserEventStatus/VisitRecord FK.
- q matches personal_entry.title and personal_entry.location_name via the same FKs.
- q on visits also matches short_review.
- q on items also matches memo, category, work_title.
- q + status= filter narrow results as AND (intersection).
- Another user's records sharing the same Event never appear in the results.
- q longer than 100 chars is accepted (no 500) and silently truncated by the view.
- q consisting only of whitespace acts as no filter.
- q containing special chars (%, &) never causes a 500.
"""
import pytest

from archive.models import PersonalEntry, UserEventStatus, VisitRecord


# ---------------------------------------------------------------------------
# Statuses pages (/archive/ and /archive/statuses/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestStatusPagesQFilter:
    """q filters both /archive/ and /archive/statuses/ status_rows server-side."""

    def test_q_matches_event_title_on_archive_page(self, user_client, make_event):
        user, client = user_client()
        match_event = make_event(title="매칭 이벤트", location_name="서울")
        no_match = make_event(title="다른 이벤트", location_name="부산")
        UserEventStatus.objects.create(user=user, event=match_event, status="planned")
        UserEventStatus.objects.create(user=user, event=no_match, status="planned")

        resp = client.get("/archive/?q=매칭")

        assert resp.status_code == 200
        titles = [row["subject"]["title"] for row in resp.context["status_rows"]]
        assert "매칭 이벤트" in titles
        assert "다른 이벤트" not in titles

    def test_q_matches_event_location_on_statuses_page(self, user_client, make_event):
        user, client = user_client()
        match_event = make_event(title="이벤트A", location_name="홍대 카페")
        no_match = make_event(title="이벤트B", location_name="강남")
        UserEventStatus.objects.create(user=user, event=match_event, status="planned")
        UserEventStatus.objects.create(user=user, event=no_match, status="planned")

        resp = client.get("/archive/statuses/?q=홍대")

        assert resp.status_code == 200
        titles = [row["subject"]["title"] for row in resp.context["status_rows"]]
        assert "이벤트A" in titles
        assert "이벤트B" not in titles

    def test_q_matches_personal_entry_title_on_statuses_page(self, user_client):
        user, client = user_client()
        entry_match = PersonalEntry.objects.create(
            user=user, kind=PersonalEntry.Kind.PLACE, title="매칭 카페"
        )
        entry_no = PersonalEntry.objects.create(
            user=user, kind=PersonalEntry.Kind.PLACE, title="다른 항목"
        )
        UserEventStatus.objects.create(user=user, personal_entry=entry_match, status="planned")
        UserEventStatus.objects.create(user=user, personal_entry=entry_no, status="planned")

        resp = client.get("/archive/statuses/?q=매칭")

        assert resp.status_code == 200
        titles = [row["subject"]["title"] for row in resp.context["status_rows"]]
        assert "매칭 카페" in titles
        assert "다른 항목" not in titles

    def test_q_matches_personal_entry_location_on_statuses_page(self, user_client):
        user, client = user_client()
        entry_match = PersonalEntry.objects.create(
            user=user, kind=PersonalEntry.Kind.PLACE, title="A항목",
            location_name="신촌 골목",
        )
        entry_no = PersonalEntry.objects.create(
            user=user, kind=PersonalEntry.Kind.PLACE, title="B항목",
            location_name="이태원",
        )
        UserEventStatus.objects.create(user=user, personal_entry=entry_match, status="planned")
        UserEventStatus.objects.create(user=user, personal_entry=entry_no, status="planned")

        resp = client.get("/archive/statuses/?q=신촌")

        titles = [row["subject"]["title"] for row in resp.context["status_rows"]]
        assert "A항목" in titles
        assert "B항목" not in titles

    def test_q_and_status_narrow_as_intersection(self, user_client, make_event):
        """q + status=planned → only rows matching BOTH filters."""
        user, client = user_client()
        # planned AND title matches q
        match_plan = make_event(title="매칭 계획")
        UserEventStatus.objects.create(user=user, event=match_plan, status="planned")
        # planned but title does NOT match q
        no_match_plan = make_event(title="다른 계획")
        UserEventStatus.objects.create(user=user, event=no_match_plan, status="planned")
        # title matches q but status is visited (not planned)
        match_visit = make_event(title="매칭 방문")
        UserEventStatus.objects.create(user=user, event=match_visit, status="visited")

        resp = client.get("/archive/statuses/?status=planned&q=매칭")

        assert resp.status_code == 200
        titles = [row["subject"]["title"] for row in resp.context["status_rows"]]
        assert "매칭 계획" in titles
        assert "다른 계획" not in titles
        assert "매칭 방문" not in titles

    def test_q_context_key_on_statuses_page(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/statuses/?q=검색어")

        assert resp.context["q"] == "검색어"
        assert resp.context["has_query"] is True

    def test_q_context_key_on_archive_page(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/?q=test")

        assert resp.context["q"] == "test"
        assert resp.context["has_query"] is True

    def test_pager_query_preserves_both_status_and_q(self, user_client, make_event):
        user, client = user_client()
        # Create enough rows so 2 pages exist
        for i in range(7):
            ev = make_event(title=f"매칭 {i:02d}")
            UserEventStatus.objects.create(user=user, event=ev, status="planned")

        resp = client.get("/archive/statuses/?status=planned&q=매칭")

        assert resp.status_code == 200
        pager_query = resp.context["pager_query"]
        assert "status=planned" in pager_query
        assert "q=" in pager_query


# ---------------------------------------------------------------------------
# Visits page (/archive/visits/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestVisitsPageQFilter:
    """q filters visit_rows on /archive/visits/ including short_review."""

    def test_q_matches_event_title(self, user_client, make_event):
        user, client = user_client()
        match_ev = make_event(title="매칭 팝업")
        no_match_ev = make_event(title="다른 팝업")
        VisitRecord.objects.create(user=user, event=match_ev, visited_on="2026-06-01")
        VisitRecord.objects.create(user=user, event=no_match_ev, visited_on="2026-06-02")

        resp = client.get("/archive/visits/?q=매칭")

        assert resp.status_code == 200
        titles = [row["subject"]["title"] for row in resp.context["visit_rows"]]
        assert "매칭 팝업" in titles
        assert "다른 팝업" not in titles

    def test_q_matches_event_location(self, user_client, make_event):
        user, client = user_client()
        match_ev = make_event(title="팝업A", location_name="성수 거리")
        no_match_ev = make_event(title="팝업B", location_name="강남역")
        VisitRecord.objects.create(user=user, event=match_ev, visited_on="2026-06-01")
        VisitRecord.objects.create(user=user, event=no_match_ev, visited_on="2026-06-02")

        resp = client.get("/archive/visits/?q=성수")

        titles = [row["subject"]["title"] for row in resp.context["visit_rows"]]
        assert "팝업A" in titles
        assert "팝업B" not in titles

    def test_q_matches_short_review(self, user_client, make_event):
        user, client = user_client()
        ev_with_review = make_event(title="행사A")
        ev_no_match = make_event(title="행사B")
        VisitRecord.objects.create(
            user=user, event=ev_with_review, visited_on="2026-06-01",
            short_review="굉장히 재미있었다",
        )
        VisitRecord.objects.create(
            user=user, event=ev_no_match, visited_on="2026-06-02",
            short_review="별로",
        )

        resp = client.get("/archive/visits/?q=굉장히")

        titles = [row["subject"]["title"] for row in resp.context["visit_rows"]]
        assert "행사A" in titles
        assert "행사B" not in titles

    def test_q_matches_personal_entry_title_on_visits(self, user_client):
        user, client = user_client()
        entry_match = PersonalEntry.objects.create(
            user=user, kind=PersonalEntry.Kind.PLACE, title="비공식 매칭"
        )
        entry_no = PersonalEntry.objects.create(
            user=user, kind=PersonalEntry.Kind.PLACE, title="비공식 아님"
        )
        VisitRecord.objects.create(user=user, personal_entry=entry_match, visited_on="2026-06-01")
        VisitRecord.objects.create(user=user, personal_entry=entry_no, visited_on="2026-06-02")

        resp = client.get("/archive/visits/?q=매칭")

        titles = [row["subject"]["title"] for row in resp.context["visit_rows"]]
        assert "비공식 매칭" in titles
        assert "비공식 아님" not in titles

    def test_q_and_filter_narrow_as_intersection(self, user_client, make_event):
        """filter=unofficial AND q → only unofficial rows matching q."""
        user, client = user_client()
        # unofficial matching
        entry_match = PersonalEntry.objects.create(
            user=user, kind=PersonalEntry.Kind.PLACE, title="비공식 매칭"
        )
        VisitRecord.objects.create(user=user, personal_entry=entry_match, visited_on="2026-06-03")
        # official matching title (but filter=unofficial excludes it)
        official_ev = make_event(title="공식 매칭")
        VisitRecord.objects.create(user=user, event=official_ev, visited_on="2026-06-02")
        # unofficial not matching
        entry_no = PersonalEntry.objects.create(
            user=user, kind=PersonalEntry.Kind.PLACE, title="비공식 아님"
        )
        VisitRecord.objects.create(user=user, personal_entry=entry_no, visited_on="2026-06-01")

        resp = client.get("/archive/visits/?filter=unofficial&q=매칭")

        assert resp.status_code == 200
        titles = [row["subject"]["title"] for row in resp.context["visit_rows"]]
        assert "비공식 매칭" in titles
        assert "공식 매칭" not in titles
        assert "비공식 아님" not in titles

    def test_q_context_on_visits_page(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/visits/?q=찾기")

        assert resp.context["q"] == "찾기"
        assert resp.context["has_query"] is True


# ---------------------------------------------------------------------------
# Items page (/archive/items/)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestItemsPageQFilter:
    """q filters entry_rows on /archive/items/."""

    def test_q_matches_title(self, user_client):
        user, client = user_client()
        PersonalEntry.objects.create(user=user, kind=PersonalEntry.Kind.PLACE, title="매칭 항목")
        PersonalEntry.objects.create(user=user, kind=PersonalEntry.Kind.PLACE, title="다른 항목")

        resp = client.get("/archive/items/?q=매칭")

        assert resp.status_code == 200
        titles = [row["entry"].title for row in resp.context["entry_rows"]]
        assert "매칭 항목" in titles
        assert "다른 항목" not in titles

    def test_q_matches_memo(self, user_client):
        user, client = user_client()
        PersonalEntry.objects.create(
            user=user, kind=PersonalEntry.Kind.PLACE, title="A", memo="특별한 내용"
        )
        PersonalEntry.objects.create(
            user=user, kind=PersonalEntry.Kind.PLACE, title="B", memo="보통 내용"
        )

        resp = client.get("/archive/items/?q=특별한")

        titles = [row["entry"].title for row in resp.context["entry_rows"]]
        assert "A" in titles
        assert "B" not in titles

    def test_q_matches_location(self, user_client):
        user, client = user_client()
        PersonalEntry.objects.create(
            user=user, kind=PersonalEntry.Kind.PLACE, title="A", location_name="신촌"
        )
        PersonalEntry.objects.create(
            user=user, kind=PersonalEntry.Kind.PLACE, title="B", location_name="강남"
        )

        resp = client.get("/archive/items/?q=신촌")

        titles = [row["entry"].title for row in resp.context["entry_rows"]]
        assert "A" in titles
        assert "B" not in titles

    def test_q_matches_work_title(self, user_client):
        user, client = user_client()
        PersonalEntry.objects.create(
            user=user, kind=PersonalEntry.Kind.GOODS, title="A", work_title="원피스 콜라보"
        )
        PersonalEntry.objects.create(
            user=user, kind=PersonalEntry.Kind.GOODS, title="B", work_title="블리치"
        )

        resp = client.get("/archive/items/?q=원피스")

        titles = [row["entry"].title for row in resp.context["entry_rows"]]
        assert "A" in titles
        assert "B" not in titles

    def test_q_matches_category(self, user_client):
        user, client = user_client()
        PersonalEntry.objects.create(
            user=user, kind=PersonalEntry.Kind.PLACE, title="A", category="팝업스토어"
        )
        PersonalEntry.objects.create(
            user=user, kind=PersonalEntry.Kind.PLACE, title="B", category="카페"
        )

        resp = client.get("/archive/items/?q=팝업")

        titles = [row["entry"].title for row in resp.context["entry_rows"]]
        assert "A" in titles
        assert "B" not in titles


# ---------------------------------------------------------------------------
# Cross-cutting: user isolation, q normalisation, special chars
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestArchiveSearchIsolation:
    """Another user's records sharing the same Event must not appear in q results."""

    def test_statuses_q_does_not_leak_other_user_rows(self, user_client, make_event):
        user_a, client_a = user_client(username="userA")
        user_b, _ = user_client(username="userB")

        shared_event = make_event(title="공유 이벤트")
        UserEventStatus.objects.create(user=user_a, event=shared_event, status="planned")
        UserEventStatus.objects.create(user=user_b, event=shared_event, status="planned")

        resp = client_a.get("/archive/statuses/?q=공유")

        assert resp.status_code == 200
        # Should see exactly 1 row — user A's own status, not user B's.
        assert resp.context["page_obj"].paginator.count == 1

    def test_visits_q_does_not_leak_other_user_rows(self, user_client, make_event):
        user_a, client_a = user_client(username="visitorA")
        user_b, _ = user_client(username="visitorB")

        shared_event = make_event(title="공유 팝업")
        VisitRecord.objects.create(user=user_a, event=shared_event, visited_on="2026-06-01")
        VisitRecord.objects.create(user=user_b, event=shared_event, visited_on="2026-06-01")

        resp = client_a.get("/archive/visits/?q=공유")

        assert resp.status_code == 200
        assert resp.context["page_obj"].paginator.count == 1


@pytest.mark.django_db
class TestQNormalisation:
    """q is strip()[:100]-normalised before filtering."""

    def test_whitespace_only_q_acts_as_no_filter(self, user_client):
        user, client = user_client()
        PersonalEntry.objects.create(user=user, kind=PersonalEntry.Kind.PLACE, title="항목 A")
        PersonalEntry.objects.create(user=user, kind=PersonalEntry.Kind.PLACE, title="항목 B")

        resp = client.get("/archive/items/?q=   ")

        assert resp.status_code == 200
        assert resp.context["q"] == ""
        assert resp.context["has_query"] is False
        # All entries still returned (no filter applied)
        assert resp.context["page_obj"].paginator.count == 2

    def test_long_q_truncated_no_server_error(self, user_client):
        _, client = user_client()

        resp = client.get("/archive/items/?q=" + "A" * 200)

        assert resp.status_code == 200

    def test_q_special_chars_no_500_on_archive(self, user_client):
        _, client = user_client()

        for special_q in ("a%b", "x&y=z", "<script>"):
            resp = client.get(f"/archive/?q={special_q}")
            assert resp.status_code == 200, f"500 on q={special_q!r}"

    def test_q_special_chars_no_500_on_visits(self, user_client):
        _, client = user_client()

        for special_q in ("a%b", "x&y=z", "<script>"):
            resp = client.get(f"/archive/visits/?q={special_q}")
            assert resp.status_code == 200, f"500 on q={special_q!r}"
