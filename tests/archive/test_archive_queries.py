"""Unit tests for the archive read layer (archive/queries.py)."""

import pytest

from archive.models import CollectionItem, EventInterest, PersonalEntry, UserEventStatus, VisitRecord
from archive.queries import (
    ARCHIVE_STATUS_SLUGS,
    list_user_collection_items,
    list_user_interests,
    list_user_personal_entries,
    list_user_planned_events,
    list_user_statuses,
    list_user_visit_records,
    user_interest_count,
    user_interest_event_ids,
    user_personal_entry_counts,
    user_personal_interest_ids,
    user_personal_statuses,
    user_status_counts,
    user_visit_record_counts,
)


@pytest.mark.django_db
def test_user_status_counts_zero_fills_all_slugs(make_user):
    """A user with no statuses gets every canonical slug present and zero."""
    user = make_user(username="counts-empty")

    counts = user_status_counts(user)

    assert set(counts) == set(ARCHIVE_STATUS_SLUGS)
    assert all(value == 0 for value in counts.values())


@pytest.mark.django_db
def test_user_status_counts_counts_per_status(make_user, make_event, make_status):
    """Counts reflect the user's rows and ignore other users' rows."""
    user = make_user(username="counts-user")
    other = make_user(username="counts-other")
    e1 = make_event(title="E1")
    e2 = make_event(title="E2")

    make_status(user, event=e1, status="planned")
    make_status(user, event=e2, status="visited")
    make_status(other, event=e1, status="planned")

    counts = user_status_counts(user)

    assert counts["planned"] == 1
    assert counts["visited"] == 1
    assert counts["missed"] == 0


@pytest.mark.django_db
def test_list_user_statuses_filters_by_user_and_status(make_user, make_event, make_status):
    user = make_user(username="list-status-user")
    other = make_user(username="list-status-other")
    e1 = make_event(title="E1")
    e2 = make_event(title="E2")

    make_status(user, event=e1, status="planned")
    make_status(user, event=e2, status="visited")
    make_status(other, event=e1, status="planned")

    assert list_user_statuses(user).count() == 2
    planned_only = list_user_statuses(user, "planned")
    assert planned_only.count() == 1
    assert planned_only.first().event_id == e1.id


@pytest.mark.django_db
def test_list_user_visit_records_scoped_and_ordered(make_user, make_event, make_visit):
    user = make_user(username="list-visit-user")
    other = make_user(username="list-visit-other")
    e1 = make_event(title="E1")
    e2 = make_event(title="E2")

    older = make_visit(user, event=e1, visited_on="2026-05-01")
    newer = make_visit(user, event=e2, visited_on="2026-06-01")
    make_visit(other, event=e1, visited_on="2026-06-15")

    rows = list(list_user_visit_records(user))

    assert [r.id for r in rows] == [newer.id, older.id]


@pytest.mark.django_db
def test_list_user_visit_records_official_only(make_event, make_user):
    """official=True excludes visits attached to a private PersonalEntry
    (moved from tests/core/test_coverage_supplements.py)."""
    user = make_user()
    event = make_event(title="공식 방문")
    entry = PersonalEntry.objects.create(
        user=user, kind=PersonalEntry.Kind.PLACE, title="비공식 방문"
    )
    VisitRecord.objects.create(user=user, event=event, visited_on="2026-01-01")
    VisitRecord.objects.create(user=user, personal_entry=entry, visited_on="2026-01-02")

    official = list(list_user_visit_records(user, official=True))

    assert all(r.event_id is not None for r in official)
    assert len(official) == 1


# ---------------------------------------------------------------------------
# ARCHIVE_STATUS_SLUGS no longer contains "interested"
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_archive_status_slugs_excludes_interested(django_user_model):
    assert "interested" not in ARCHIVE_STATUS_SLUGS
    assert "planned" in ARCHIVE_STATUS_SLUGS
    assert "visited" in ARCHIVE_STATUS_SLUGS
    assert "missed" in ARCHIVE_STATUS_SLUGS


# ---------------------------------------------------------------------------
# user_status_counts — interested not counted even if row exists at DB level
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_status_counts_excludes_interested_key(make_user):
    """user_status_counts must not include 'interested' as a key."""
    user = make_user(username="counts-no-interested")
    counts = user_status_counts(user)
    assert "interested" not in counts


# ---------------------------------------------------------------------------
# list_user_interests — scoped to user, select_related event, newest-first
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_list_user_interests_scoped_and_ordered(make_user, make_event, make_interest):
    user = make_user(username="interest-query-user")
    other = make_user(username="interest-query-other")
    e1 = make_event(title="Interest E1")
    e2 = make_event(title="Interest E2")
    e3 = make_event(title="Interest E3")

    first = make_interest(user, event=e1)
    second = make_interest(user, event=e2)
    make_interest(other, event=e3)

    rows = list(list_user_interests(user))

    assert len(rows) == 2
    assert rows[0].pk == second.pk
    assert rows[1].pk == first.pk
    assert rows[0].event.id == e2.id


# ---------------------------------------------------------------------------
# user_interest_event_ids — returns {event_id: interest_id} bounded by ids
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_interest_event_ids_bounded(make_user, make_event, make_interest):
    user = make_user(username="interest-ids-user")
    other = make_user(username="interest-ids-other")
    e1 = make_event(title="Interest IDs E1")
    e2 = make_event(title="Interest IDs E2")
    e3 = make_event(title="Interest IDs E3")

    i1 = make_interest(user, event=e1)
    make_interest(user, event=e2)
    make_interest(other, event=e3)

    result = user_interest_event_ids(user, event_ids=[e1.id, e3.id])

    assert result == {e1.id: i1.pk}


@pytest.mark.django_db
def test_user_interest_event_ids_unbounded(make_user, make_event, make_interest):
    user = make_user(username="interest-ids-unbound-user")
    e1 = make_event(title="Interest Unbound E1")
    e2 = make_event(title="Interest Unbound E2")

    i1 = make_interest(user, event=e1)
    i2 = make_interest(user, event=e2)

    result = user_interest_event_ids(user)

    assert result == {e1.id: i1.pk, e2.id: i2.pk}


# ---------------------------------------------------------------------------
# user_interest_count
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_interest_count(make_user, make_event, make_interest):
    user = make_user(username="interest-count-user")
    other = make_user(username="interest-count-other")
    e1 = make_event(title="Interest Count E1")
    e2 = make_event(title="Interest Count E2")
    e3 = make_event(title="Interest Count E3")

    make_interest(user, event=e1)
    make_interest(user, event=e2)
    make_interest(other, event=e3)

    assert user_interest_count(user) == 2


# ---------------------------------------------------------------------------
# list_user_planned_events (selectable set when adding a visit record)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_list_user_planned_events_returns_only_user_planned_published(make_user, make_event, make_draft_event, make_status):
    user = make_user(username="planner")
    other = make_user(username="planner-other")
    planned = make_event(title="Planned")
    visited = make_event(title="Visited")
    missed = make_event(title="Missed")
    others_planned = make_event(title="Others planned")
    draft_planned = make_draft_event(title="Draft planned")

    make_status(user, event=planned, status="planned")
    make_status(user, event=visited, status="visited")
    make_status(user, event=missed, status="missed")
    make_status(user, event=draft_planned, status="planned")
    make_status(other, event=others_planned, status="planned")

    events = list(list_user_planned_events(user))

    assert planned in events
    assert visited not in events  # different status
    assert missed not in events  # different status
    assert others_planned not in events  # different user
    assert draft_planned not in events  # not published


# ---------------------------------------------------------------------------
# list_user_personal_entries
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_list_user_personal_entries_scopes_to_user_and_filters_kind(make_user, make_entry):
    user = make_user(username="pe-list")
    other = make_user(username="pe-other")
    place = make_entry(user, kind="place", title="P")
    goods = make_entry(user, kind="goods", title="G")
    make_entry(other, kind="place", title="Other P")

    all_entries = list(list_user_personal_entries(user))
    assert place in all_entries
    assert goods in all_entries
    assert len(all_entries) == 2  # other user's entry excluded

    only_goods = list(list_user_personal_entries(user, kind="goods"))
    assert only_goods == [goods]


# ---------------------------------------------------------------------------
# user_visit_record_counts (archive/visits/ summary cards)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_visit_record_counts_totals_and_memo_scoped_to_user(
    make_user, make_event, make_visit
):
    user = make_user(username="visit-counts-user")
    other = make_user(username="visit-counts-other")
    e1 = make_event(title="VC E1")
    e2 = make_event(title="VC E2")
    e3 = make_event(title="VC E3")

    make_visit(user, event=e1, visited_on="2026-01-01", short_review="좋았음")
    make_visit(user, event=e2, visited_on="2026-01-02", short_review="")
    make_visit(other, event=e3, visited_on="2026-01-03", short_review="다른 사용자")

    counts = user_visit_record_counts(user)

    assert counts == {"total_count": 2, "memo_count": 1}


@pytest.mark.django_db
def test_user_visit_record_counts_zero_for_no_visits(make_user):
    user = make_user(username="visit-counts-empty")

    counts = user_visit_record_counts(user)

    assert counts == {"total_count": 0, "memo_count": 0}


# ---------------------------------------------------------------------------
# user_personal_entry_counts (archive/items/ summary cards)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_personal_entry_counts_totals_scoped_to_user(make_user, make_entry):
    user = make_user(username="entry-counts-user")
    other = make_user(username="entry-counts-other")
    make_entry(user, kind=PersonalEntry.Kind.PLACE, title="P1")
    make_entry(user, kind=PersonalEntry.Kind.PLACE, title="P2")
    make_entry(other, kind=PersonalEntry.Kind.PLACE, title="Other P")

    counts = user_personal_entry_counts(user)

    assert counts == {"total_count": 2}


@pytest.mark.django_db
def test_user_personal_entry_counts_zero_for_no_entries(make_user):
    user = make_user(username="entry-counts-empty")

    counts = user_personal_entry_counts(user)

    assert counts == {"total_count": 0}


# ---------------------------------------------------------------------------
# list_user_collection_items (PR-C1)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_list_user_collection_items_scopes_to_owner(make_user):
    user = make_user(username="ci-query-owner")
    other = make_user(username="ci-query-other")
    mine = CollectionItem.objects.create(user=user, name="내 굿즈")
    CollectionItem.objects.create(user=other, name="남의 굿즈")

    items = list(list_user_collection_items(user))

    assert items == [mine]


# ---------------------------------------------------------------------------
# list_user_collection_items filters (PR-C5, CP16~22). `duplicate`/
# `tradeable` are *derived* from quantity/tradeable_quantity — CollectionItem
# has no separate duplicate_count or tradeable flag field (§3-1).
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_list_user_collection_items_work_title_filter_is_exact_match(make_user):
    user = make_user(username="ci-query-work-title")
    match = CollectionItem.objects.create(user=user, name="일치", work_title="작품 A")
    CollectionItem.objects.create(user=user, name="불일치", work_title="작품 B")

    items = list(list_user_collection_items(user, work_title="작품 A"))

    assert items == [match]


@pytest.mark.django_db
def test_list_user_collection_items_duplicate_filter_derives_from_quantity_gte_2(make_user):
    """`duplicate=True` must select quantity >= 2 rows — there is no
    duplicate_count field to filter on directly (§3-1)."""
    user = make_user(username="ci-query-duplicate")
    two = CollectionItem.objects.create(user=user, name="둘", quantity=2)
    one = CollectionItem.objects.create(user=user, name="하나", quantity=1)

    assert list(list_user_collection_items(user, duplicate=True)) == [two]
    assert list(list_user_collection_items(user, duplicate=False)) == [one]
    assert not hasattr(two, "duplicate_count")


@pytest.mark.django_db
def test_list_user_collection_items_tradeable_filter_derives_from_tradeable_quantity_gt_0(
    make_user,
):
    """`tradeable=True` must select tradeable_quantity > 0 rows — there is
    no separate tradeable flag field (§3-1)."""
    user = make_user(username="ci-query-tradeable")
    tradeable = CollectionItem.objects.create(
        user=user, name="교환 가능", quantity=3, tradeable_quantity=1
    )
    not_tradeable = CollectionItem.objects.create(
        user=user, name="교환 불가", quantity=3, tradeable_quantity=0
    )

    assert list(list_user_collection_items(user, tradeable=True)) == [tradeable]
    assert list(list_user_collection_items(user, tradeable=False)) == [not_tradeable]


@pytest.mark.django_db
def test_list_user_collection_items_q_matches_name_work_title_character_name_or_memo(
    make_user,
):
    """`q` narrows to name/work_title/character_name/memo (icontains), mirroring
    list_user_personal_entries' q pattern. item_type is deliberately NOT a q
    target field — a decoy row matching only on item_type must be excluded."""
    user = make_user(username="ci-query-q")
    other = make_user(username="ci-query-q-other")
    by_name = CollectionItem.objects.create(user=user, name="레어 스탬프")
    by_work_title = CollectionItem.objects.create(
        user=user, name="굿즈 1", work_title="레어 작품"
    )
    by_character_name = CollectionItem.objects.create(
        user=user, name="굿즈 2", character_name="레어 캐릭터"
    )
    by_memo = CollectionItem.objects.create(user=user, name="굿즈 3", memo="레어 메모")
    item_type_decoy = CollectionItem.objects.create(
        user=user, name="굿즈 4", item_type="레어 타입"
    )
    other_user_same_name = CollectionItem.objects.create(user=other, name="레어 스탬프")

    items = set(list_user_collection_items(user, q="레어"))

    assert items == {by_name, by_work_title, by_character_name, by_memo}
    assert item_type_decoy not in items
    assert other_user_same_name not in items


@pytest.mark.django_db
def test_list_user_collection_items_empty_q_is_a_no_op(make_user):
    """An empty `q` must not filter anything out — mirrors the other list_*
    functions' `if q:` guard (a `q is not None` guard would wrongly filter
    every row to an empty-string match)."""
    user = make_user(username="ci-query-q-empty")
    first = CollectionItem.objects.create(user=user, name="굿즈 1")
    second = CollectionItem.objects.create(user=user, name="굿즈 2")

    items = set(list_user_collection_items(user, q=""))

    assert items == {first, second}


# ---------------------------------------------------------------------------
# user_personal_interest_ids / user_personal_statuses — exclude goods rows
# (defensive filter against pre-C4 transitional data; goods can no longer be
# created as an interest/status subject, but ORM-created rows simulate a
# leftover from before the gate existed — collection domain design plan §3-3)
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_user_personal_interest_ids_excludes_goods(make_user):
    user = make_user(username="interest-ids-goods")
    place = PersonalEntry.objects.create(user=user, kind=PersonalEntry.Kind.PLACE, title="장소")
    goods = PersonalEntry.objects.create(user=user, kind="goods", title="굿즈")
    place_interest = EventInterest.objects.create(user=user, personal_entry=place)
    EventInterest.objects.create(user=user, personal_entry=goods)

    result = user_personal_interest_ids(user)

    assert result == {place.id: place_interest.id}


@pytest.mark.django_db
def test_user_personal_statuses_excludes_goods(make_user):
    user = make_user(username="statuses-goods")
    place = PersonalEntry.objects.create(user=user, kind=PersonalEntry.Kind.PLACE, title="장소")
    goods = PersonalEntry.objects.create(user=user, kind="goods", title="굿즈")
    place_status = UserEventStatus.objects.create(
        user=user, personal_entry=place, status=UserEventStatus.Status.PLANNED
    )
    UserEventStatus.objects.create(
        user=user, personal_entry=goods, status=UserEventStatus.Status.PLANNED
    )

    result = user_personal_statuses(user)

    assert result == {place.id: (UserEventStatus.Status.PLANNED, place_status.id)}
