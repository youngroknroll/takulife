from django.db import IntegrityError, transaction

from core.analytics import record_event
from core.models import AnalyticsEvent

from .models import (
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
    """Create a private, user-owned unofficial archive item (place or goods)."""
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


def mark_missed(*, user_event_status):
    """Explicitly set a status row to missed. Works before or after the date."""
    user_event_status.status = UserEventStatus.Status.MISSED
    user_event_status.save(update_fields=["status", "updated_at"])
    return user_event_status


def revert_to_planned(*, user_event_status):
    """Pin a row back to planned and opt it out of auto-miss.

    Setting ``missed_overridden`` is what makes the choice stick: otherwise the
    read-time derivation would re-show an ended planned row as missed.
    """
    user_event_status.status = UserEventStatus.Status.PLANNED
    user_event_status.missed_overridden = True
    user_event_status.save(update_fields=["status", "missed_overridden", "updated_at"])
    return user_event_status


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
