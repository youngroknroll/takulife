import logging

from django.db import IntegrityError, transaction
from django.utils import timezone

from core.vocab import is_valid_category, is_valid_region

from .models import Event

logger = logging.getLogger(__name__)


def set_event_poster(*, event, image):
    """이벤트에 새 포스터 이미지를 지정한다.

    새 이미지를 먼저 저장하고, 옛 파일 삭제는 최선노력으로만 시도한다. 삭제가
    실패해도 업로드 자체는 성공으로 남긴다(로그만 남김). 옛 파일명을 미리 문자열로
    떼어두는 이유는, FieldFile.delete()가 모델 인스턴스에 부작용을 일으켜 방금
    저장한 새 값을 덮어쓰는 것을 막기 위해서다.
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
    """이벤트의 포스터 이미지를 제거하고 저장소 파일도 함께 지운다."""
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
    """create_published_event와 update_published_event가 공유하는 불변식 검사.

    existing_queryset으로 official_url 중복 검사 범위를 정한다. 수정 시에는 자기 자신을
    제외해야, 같은 URL을 그대로 저장해도 자기 자신과 충돌 처리되지 않는다.
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

    # category/region은 모델에 choices가 없어, 여기 어휘 검사만이 임의로 만든 POST 요청이
    # DB에 자유 문자열을 넣는 것을 막는 유일한 장치다(스태프 콘솔 select는 힌트일 뿐).
    # 빈 문자열은 둘 다 허용(미분류 / 지역 미상).
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
    """기존 이벤트의 수정 가능 필드를 갱신한다.

    publish_status와 poster_image는 여기서 건드리지 않는다(각각 별도 함수 책임:
    set_event_poster/clear_event_poster, 게시 상태 전환 함수들).
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
    """이벤트를 draft 상태로 내린다(게시 중단).

    draft는 항상 유효한 상태라 별도 검증이 필요 없다. 반대로 아래 republish_event는
    다시 게시 집합에 들어가므로 title/official_url 불변식을 재검증한다.
    """
    event.publish_status = Event.PublishStatus.DRAFT
    event.save(update_fields=["publish_status"])
    return event


def republish_event(*, event):
    """draft 이벤트를 다시 게시 상태로 되돌린다.

    create/update_published_event와 같은 불변식을 재검사한다. 게시 중단 상태에서
    다른 경로로 잘못된 값이 들어간 뒤 검증 없이 재게시되는 구멍을 막기 위해서다.
    """
    _validate_publish_fields(
        title=event.title,
        official_url=event.official_url,
        start_date=event.start_date,
        end_date=event.end_date,
        category=event.category,
        region=event.region,
        existing_queryset=Event.objects.exclude(pk=event.pk),
    )
    event.publish_status = Event.PublishStatus.PUBLISHED
    event.save(update_fields=["publish_status"])
    return event


def mark_event_verified(*, event):
    """이벤트를 지금 시각으로 수동 검증 완료 처리한다. verified_at이 null이면 미검증 상태다."""
    event.verified_at = timezone.now()
    event.save(update_fields=["verified_at"])
    return event


def hard_delete_event(*, event):
    """이벤트를 영구 삭제한다. 포스터 파일도 먼저 정리한다.

    events는 archive 모델을 알면 안 된다(경계 규칙, tests/test_architecture_boundaries.py
    참고). 삭제해도 안전한지 확인하는 책임은 호출부에 있다(예: staff/services.py의
    delete_event가 archive 참조 여부를 먼저 확인).
    """
    if event.poster_image:
        clear_event_poster(event=event)
    event.delete()
