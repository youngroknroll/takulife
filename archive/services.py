from django.db import IntegrityError, transaction

from .models import UserEventStatus


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
