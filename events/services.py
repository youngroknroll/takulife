import logging

from django.db import IntegrityError, transaction

from core.vocab import is_valid_category, is_valid_region

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


class PublishEventCategoryError(PublishEventError):
    pass


class PublishEventRegionError(PublishEventError):
    pass


def _validate_publish_fields(
    *, title, official_url, start_date, end_date, category, region, existing_queryset
):
    """Shared invariant checks for create_published_event and update_published_event.

    `existing_queryset` scopes the official_url uniqueness check: the full
    Event queryset for create, or Event.objects.exclude(pk=event.pk) for
    update (so keeping the same URL on save is not a self-conflict).

    Returns (normalized_title, normalized_official_url); raises the domain
    errors documented on the two public functions above.
    """
    normalized_official_url = (official_url or "").strip()
    if not normalized_official_url:
        raise MissingOfficialUrlError

    normalized_title = (title or "").strip()
    if not normalized_title:
        raise PublishEventTitleError

    if normalized_title.rstrip("/") == normalized_official_url.rstrip("/"):
        raise PublishEventTitleError

    if existing_queryset.filter(official_url=normalized_official_url).exists():
        raise DuplicateOfficialUrlError

    if start_date is not None and end_date is not None and start_date > end_date:
        raise InvalidEventPeriodError

    # Vocabulary membership (2026-07-23). Neither field has `choices`, so this
    # is the only thing standing between a hand-made staff POST and free text
    # in the DB — the staff console's <select> is a client-side hint, not a
    # constraint. "" stays valid on both (미분류 / 지역 미상).
    if not is_valid_category(category or ""):
        raise PublishEventCategoryError
    if not is_valid_region(region or ""):
        raise PublishEventRegionError

    return normalized_title, normalized_official_url


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
    _normalized_title, normalized_official_url = _validate_publish_fields(
        title=title,
        official_url=official_url,
        start_date=start_date,
        end_date=end_date,
        category=category,
        region=region,
        existing_queryset=Event.objects.all(),
    )

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


def update_published_event(
    *,
    event,
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
    """Update an existing event's editable fields in place.

    Reuses create_published_event's invariants via _validate_publish_fields,
    scoping the official_url uniqueness check to exclude `event` itself so
    re-saving with the same URL is not treated as a conflict. Does not touch
    publish_status or poster_image — those are out of this service's scope
    (see events/services.py's set_event_poster/clear_event_poster and the
    PR-E3 publish-status toggle).
    """
    _normalized_title, normalized_official_url = _validate_publish_fields(
        title=title,
        official_url=official_url,
        start_date=start_date,
        end_date=end_date,
        category=category,
        region=region,
        existing_queryset=Event.objects.exclude(pk=event.pk),
    )

    event.title = title
    event.category = category
    event.work_title = work_title
    event.location_name = location_name
    event.region = region
    event.start_date = start_date
    event.end_date = end_date
    event.official_url = normalized_official_url
    event.source_name = source_name
    event.summary = summary

    try:
        with transaction.atomic():
            event.save(
                update_fields=[
                    "title",
                    "category",
                    "work_title",
                    "location_name",
                    "region",
                    "start_date",
                    "end_date",
                    "official_url",
                    "source_name",
                    "summary",
                ]
            )
    except IntegrityError as exc:
        raise DuplicateOfficialUrlError from exc
    except Exception as exc:
        logger.exception("Failed to update published event pk=%s", event.pk)
        raise PublishEventError from exc

    return event


def unpublish_event(*, event):
    """Move a published (or draft) event to draft ("take down" a listing).

    No invariant checks needed — draft is always a valid state to be in,
    unlike republish_event below, which re-enters the published set and so
    must re-validate the title/official_url invariants.
    """
    event.publish_status = Event.PublishStatus.DRAFT
    event.save(update_fields=["publish_status"])
    return event


def republish_event(*, event):
    """Move a draft event back to published.

    Re-runs the same title/official_url/period invariants create_published_event
    and update_published_event share, scoped to exclude `event` itself from the
    official_url uniqueness check — this closes the gap where an event could be
    unpublished, edited into an invalid state some other way, then republished
    without ever passing through update_published_event's checks.
    """
    _validate_publish_fields(
        title=event.title,
        official_url=event.official_url,
        start_date=event.start_date,
        end_date=event.end_date,
        # Vocabulary is checked here too, for the reason this function exists:
        # a row that reached an invalid state by some other path must not slip
        # back into the published set without passing the same gate.
        category=event.category,
        region=event.region,
        existing_queryset=Event.objects.exclude(pk=event.pk),
    )
    event.publish_status = Event.PublishStatus.PUBLISHED
    event.save(update_fields=["publish_status"])
    return event


def hard_delete_event(*, event):
    """Permanently delete an event, cleaning up its poster file first.

    This is a pure primitive with no knowledge of archive models — events must
    never import archive (architecture boundary, see
    tests/test_architecture_boundaries.py). Callers are responsible for
    confirming it is safe to hard-delete (e.g. staff/services.py's
    delete_event, which checks archive references before calling this).
    """
    if event.poster_image:
        clear_event_poster(event=event)
    event.delete()
