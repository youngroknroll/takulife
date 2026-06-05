from django.db import IntegrityError, transaction

from .models import UserEventStatus


class DuplicateUserEventStatusError(Exception):
    pass


def create_user_event_status(*, user, serializer):
    with transaction.atomic():
        event = serializer.validated_data["event"]
        if UserEventStatus.objects.filter(user=user, event=event).exists():
            raise DuplicateUserEventStatusError
        try:
            return serializer.save(user=user)
        except IntegrityError as exc:
            raise DuplicateUserEventStatusError from exc
