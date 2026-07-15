from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from core.analytics import record_event
from core.models import AnalyticsEvent

from .models import (
    CollectionItem,
    EventInterest,
    PersonalEntry,
    UserEventStatus,
    VisitRecord,
    VisitRecordPhoto,
)


MAX_PHOTOS_PER_RECORD = 5

# UserEventStatus.Status -> the AnalyticsEvent recorded on creation with that
# status. MISSED has no entry: only PLANNED/VISITED are stage-0 collection
# funnel events (prompt_plan §8 PR-0e) — a status row created straight to
# MISSED has no analogous "funnel step" to record.
_STATUS_ANALYTICS_EVENT_NAME = {
    UserEventStatus.Status.PLANNED: AnalyticsEvent.EventName.EVENT_PLANNED,
    UserEventStatus.Status.VISITED: AnalyticsEvent.EventName.EVENT_MARKED_VISITED,
}


def _subject_target(*, event=None, personal_entry=None):
    """Return (target_type, target_id) for whichever subject was supplied."""
    if event is not None:
        return "event", event.id
    return "personal_entry", personal_entry.id


def create_personal_entry(*, user, kind, title, **fields):
    """Create a private, user-owned unofficial archive item.

    PersonalEntry is restricted to unofficial places (collection domain
    design plan §3-3) — goods moved to the dedicated CollectionItem domain
    and can no longer be created here.
    """
    if kind != PersonalEntry.Kind.PLACE:
        raise ValidationError({"kind": "place 외의 kind로는 PersonalEntry를 생성할 수 없습니다."})
    return PersonalEntry.objects.create(user=user, kind=kind, title=title, **fields)


class DuplicateUserEventStatusError(Exception):
    pass


class DuplicateEventInterestError(Exception):
    pass


def create_event_interest(*, user, event=None, personal_entry=None):
    with transaction.atomic():
        try:
            interest = EventInterest.objects.create(
                user=user, event=event, personal_entry=personal_entry
            )
        except IntegrityError as exc:
            raise DuplicateEventInterestError from exc
    target_type, target_id = _subject_target(event=event, personal_entry=personal_entry)
    record_event(
        AnalyticsEvent.EventName.EVENT_INTERESTED,
        user=user,
        target_type=target_type,
        target_id=target_id,
    )
    return interest


def create_user_event_status(*, user, event=None, personal_entry=None, status):
    with transaction.atomic():
        # Duplicate guard scoped to whichever subject was supplied (the model's
        # conditional unique constraints back this up at the DB level).
        existing = UserEventStatus.objects.filter(user=user)
        if event is not None:
            existing = existing.filter(event=event)
        else:
            existing = existing.filter(personal_entry=personal_entry)
        if existing.exists():
            raise DuplicateUserEventStatusError
        # Same VisitRecord invariant PATCH enforces via mark_missed/
        # revert_to_planned (§6-b Deferred): a fresh planned/missed row must
        # not be creatable for a subject that already has a VisitRecord, or
        # DELETE-then-POST would recreate the drift 0016 corrected. visited
        # is exempt — it agrees with the record instead of contradicting it.
        if status in (
            UserEventStatus.Status.PLANNED,
            UserEventStatus.Status.MISSED,
        ) and _has_visit_record(user=user, event=event, personal_entry=personal_entry):
            raise VisitRecordExistsError
        try:
            created = UserEventStatus.objects.create(
                user=user, event=event, personal_entry=personal_entry, status=status
            )
        except IntegrityError as exc:
            raise DuplicateUserEventStatusError from exc
    event_name = _STATUS_ANALYTICS_EVENT_NAME.get(status)
    if event_name is not None:
        target_type, target_id = _subject_target(event=event, personal_entry=personal_entry)
        record_event(event_name, user=user, target_type=target_type, target_id=target_id)
    return created


def mark_visited(*, user_event_status):
    """Set a status row to visited (e.g. 'I actually went')."""
    user_event_status.status = UserEventStatus.Status.VISITED
    user_event_status.save(update_fields=["status", "updated_at"])
    target_type, target_id = _subject_target(
        event=user_event_status.event, personal_entry=user_event_status.personal_entry
    )
    record_event(
        AnalyticsEvent.EventName.EVENT_MARKED_VISITED,
        user=user_event_status.user,
        target_type=target_type,
        target_id=target_id,
    )
    return user_event_status


class VisitRecordExistsError(Exception):
    """Raised when a status-only PATCH, or a fresh creation, would set a
    subject to planned or missed while it already has a VisitRecord —
    recreating the exact drift 0016 corrected (collection domain design plan
    §5 acceptance criterion 5, §6-b Deferred). The subject's VisitRecord, not
    just this status row, is the source of truth once it exists."""


def _has_visit_record(*, user, event, personal_entry):
    queryset = VisitRecord.objects.filter(user=user)
    if event is not None:
        queryset = queryset.filter(event=event)
    else:
        queryset = queryset.filter(personal_entry=personal_entry)
    return queryset.exists()


def mark_missed(*, user_event_status):
    """Explicitly set a status row to missed. Works before or after the date."""
    if _has_visit_record(
        user=user_event_status.user,
        event=user_event_status.event,
        personal_entry=user_event_status.personal_entry,
    ):
        raise VisitRecordExistsError
    user_event_status.status = UserEventStatus.Status.MISSED
    user_event_status.save(update_fields=["status", "updated_at"])
    return user_event_status


def revert_to_planned(*, user_event_status):
    """Pin a row back to planned and opt it out of auto-miss.

    Setting ``missed_overridden`` is what makes the choice stick: otherwise the
    read-time derivation would re-show an ended planned row as missed.
    """
    if _has_visit_record(
        user=user_event_status.user,
        event=user_event_status.event,
        personal_entry=user_event_status.personal_entry,
    ):
        raise VisitRecordExistsError
    user_event_status.status = UserEventStatus.Status.PLANNED
    user_event_status.missed_overridden = True
    user_event_status.save(update_fields=["status", "missed_overridden", "updated_at"])
    return user_event_status


def create_collection_item(*, user, name, visit_record=None, event=None, **fields):
    """Create a user-owned goods collection item.

    When `visit_record` is supplied, `event` is always synced from
    `visit_record.event` — a visit record's own subject wins over any
    explicitly-passed `event`, so the two links can never disagree
    (collection domain design plan §3-1 FK-pair invariant). `visit_record`
    must belong to `user` — attaching another user's visit record is
    rejected here rather than surfacing as a cross-user data leak.

    Quantity invariants (quantity >= 0, 0 <= tradeable_quantity <= quantity)
    are re-checked here as a controlled ValidationError *before* the insert
    — the DB CheckConstraints are the source of truth, this is the
    service-level half of the plan's declared "model constraint +
    application service" double guard (§3-1), not a replacement for them.
    """
    quantity = fields.get("quantity", CollectionItem._meta.get_field("quantity").default)
    tradeable_quantity = fields.get(
        "tradeable_quantity", CollectionItem._meta.get_field("tradeable_quantity").default
    )
    errors = {}
    if quantity < 0:
        errors["quantity"] = "quantity must be >= 0."
    if tradeable_quantity < 0:
        errors["tradeable_quantity"] = "tradeable_quantity must be >= 0."
    elif tradeable_quantity > quantity:
        errors["tradeable_quantity"] = "tradeable_quantity must be <= quantity."
    if errors:
        raise ValidationError(errors)

    if visit_record is not None:
        if visit_record.user_id != user.id:
            raise ValidationError(
                {"visit_record": "visit_record must belong to the requesting user."}
            )
        event = visit_record.event

    return CollectionItem.objects.create(
        user=user, name=name, visit_record=visit_record, event=event, **fields
    )


def create_visit_record(*, user, event=None, personal_entry=None, visited_on, short_review=""):
    record = VisitRecord.objects.create(
        user=user,
        event=event,
        personal_entry=personal_entry,
        visited_on=visited_on,
        short_review=short_review,
    )
    target_type, target_id = _subject_target(event=event, personal_entry=personal_entry)
    # short_review is deliberately excluded from context — it is free text a
    # user typed, one of record_event's forbidden context keys (personal data).
    record_event(
        AnalyticsEvent.EventName.VISIT_RECORD_CREATED,
        user=user,
        target_type=target_type,
        target_id=target_id,
    )
    return record


def complete_visit_with_record(
    *, user, event=None, personal_entry=None, visited_on, short_review=""
):
    """Complete a visit and record the experience together, atomically
    (collection domain design plan §3-4, F-02). The status subject is
    auto-managed so a visit record can never exist while its status row
    disagrees with "visited".
    """
    with transaction.atomic():
        existing = UserEventStatus.objects.filter(user=user)
        if event is not None:
            existing = existing.filter(event=event)
        else:
            existing = existing.filter(personal_entry=personal_entry)
        status_row = existing.first()

        if status_row is None:
            create_user_event_status(
                user=user,
                event=event,
                personal_entry=personal_entry,
                status=UserEventStatus.Status.VISITED,
            )
        elif status_row.status != UserEventStatus.Status.VISITED:
            mark_visited(user_event_status=status_row)

        return create_visit_record(
            user=user,
            event=event,
            personal_entry=personal_entry,
            visited_on=visited_on,
            short_review=short_review,
        )


def update_visit_record(*, record, visited_on, short_review):
    """Update an existing record's editable fields. Subject stays pinned."""
    record.visited_on = visited_on
    record.short_review = short_review
    record.save(update_fields=["visited_on", "short_review"])
    return record


class PhotoLimitExceededError(Exception):
    pass


def create_visit_record_photo(*, visit_record, image):
    with transaction.atomic():
        locked_record = VisitRecord.objects.select_for_update().get(pk=visit_record.pk)
        if locked_record.photos.count() >= MAX_PHOTOS_PER_RECORD:
            raise PhotoLimitExceededError
        photo = VisitRecordPhoto.objects.create(visit_record=locked_record, image=image)
    record_event(
        AnalyticsEvent.EventName.VISIT_PHOTO_ADDED,
        user=locked_record.user,
        target_type="visit_record_photo",
        target_id=photo.id,
    )
    return photo
