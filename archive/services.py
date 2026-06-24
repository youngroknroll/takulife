from django.db import IntegrityError, transaction

from .models import UserEventStatus, VisitRecord, VisitRecordPhoto


MAX_PHOTOS_PER_RECORD = 10


class DuplicateUserEventStatusError(Exception):
    pass


def create_user_event_status(*, user, event, status):
    with transaction.atomic():
        if UserEventStatus.objects.filter(user=user, event=event).exists():
            raise DuplicateUserEventStatusError
        try:
            return UserEventStatus.objects.create(user=user, event=event, status=status)
        except IntegrityError as exc:
            raise DuplicateUserEventStatusError from exc


def create_visit_record(*, user, event, visited_on, short_review=""):
    return VisitRecord.objects.create(
        user=user,
        event=event,
        visited_on=visited_on,
        short_review=short_review,
    )


class PhotoLimitExceededError(Exception):
    pass


def create_visit_record_photo(*, visit_record, image):
    if visit_record.photos.count() >= MAX_PHOTOS_PER_RECORD:
        raise PhotoLimitExceededError
    return VisitRecordPhoto.objects.create(visit_record=visit_record, image=image)
