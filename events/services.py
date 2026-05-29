import logging

from django.db import IntegrityError, transaction

from .models import Event

logger = logging.getLogger(__name__)


class DuplicateOfficialUrlError(Exception):
    pass


class PublishEventError(Exception):
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
    if Event.objects.filter(official_url=official_url).exists():
        raise DuplicateOfficialUrlError

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
                official_url=official_url,
                source_name=source_name,
                summary=summary,
                publish_status=Event.PublishStatus.PUBLISHED,
            )
    except IntegrityError as exc:
        raise DuplicateOfficialUrlError from exc
    except Exception as exc:
        logger.exception("Failed to publish event for official_url=%s", official_url)
        raise PublishEventError from exc
