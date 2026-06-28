from django.db import IntegrityError, transaction

from .models import (
    EventInterest,
    PersonalEntry,
    UserEventStatus,
    VisitRecord,
    VisitRecordPhoto,
)


MAX_PHOTOS_PER_RECORD = 5


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
            return EventInterest.objects.create(
                user=user, event=event, personal_entry=personal_entry
            )
        except IntegrityError as exc:
            raise DuplicateEventInterestError from exc


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
            return UserEventStatus.objects.create(
                user=user, event=event, personal_entry=personal_entry, status=status
            )
        except IntegrityError as exc:
            raise DuplicateUserEventStatusError from exc


def mark_visited(*, user_event_status):
    """Set a status row to visited (e.g. 'I actually went')."""
    user_event_status.status = UserEventStatus.Status.VISITED
    user_event_status.save(update_fields=["status", "updated_at"])
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
    return VisitRecord.objects.create(
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
    if visit_record.photos.count() >= MAX_PHOTOS_PER_RECORD:
        raise PhotoLimitExceededError
    return VisitRecordPhoto.objects.create(visit_record=visit_record, image=image)
