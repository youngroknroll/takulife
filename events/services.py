import logging

from django.db import IntegrityError, transaction

from .models import Event

logger = logging.getLogger(__name__)


def set_event_poster(*, event, image):
    """Assign a new poster image to an event.

    Saves the new image, then best-effort deletes the old file from storage.
    Cleanup failure is logged but never propagated — the upload always wins.
    The file path is determined by the field/storage, never by user input.

    Captures the old file name as a plain string before overwriting so that
    FieldFile.delete() side-effects on the model instance do not clobber the
    newly saved value on the event object.
    """
    old_name = event.poster_image.name if event.poster_image else None
    old_storage = event.poster_image.storage if event.poster_image else None
    event.poster_image = image
    event.save(update_fields=["poster_image"])
    if old_name and old_storage:
        try:
            old_storage.delete(old_name)
        except Exception:
            logger.exception("Failed to delete old poster image for event pk=%s", event.pk)


def clear_event_poster(*, event):
    """Remove the poster image from an event and delete the file from storage."""
    event.poster_image.delete(save=True)


class DuplicateOfficialUrlError(Exception):
    pass


class MissingOfficialUrlError(Exception):
    pass


class PublishEventError(Exception):
    pass


class InvalidEventPeriodError(PublishEventError):
    pass


class PublishEventTitleError(PublishEventError):
    pass


def create_published_event(
    *,
    title,
    category="",
    work_title="",
    location_name="",
    region="",
    start_date=None,
    end_date=None,
    official_url,
    source_name="",
    summary="",
):
    normalized_official_url = (official_url or "").strip()
    if not normalized_official_url:
        raise MissingOfficialUrlError

    normalized_title = (title or "").strip()
    if not normalized_title:
        raise PublishEventTitleError

    if normalized_title.rstrip("/") == normalized_official_url.rstrip("/"):
        raise PublishEventTitleError

    if Event.objects.filter(official_url=normalized_official_url).exists():
        raise DuplicateOfficialUrlError

    if start_date is not None and end_date is not None and start_date > end_date:
        raise InvalidEventPeriodError

    try:
        with transaction.atomic():
            return Event.objects.create(
                title=title,
                category=category,
                work_title=work_title,
                location_name=location_name,
                region=region,
                start_date=start_date,
                end_date=end_date,
                official_url=normalized_official_url,
                source_name=source_name,
                summary=summary,
                publish_status=Event.PublishStatus.PUBLISHED,
            )
    except IntegrityError as exc:
        raise DuplicateOfficialUrlError from exc
    except Exception as exc:
        logger.exception("Failed to publish event for official_url=%s", official_url)
        raise PublishEventError from exc
