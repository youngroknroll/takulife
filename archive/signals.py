import logging

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import CollectionItem, PersonalEntry, VisitRecordPhoto

logger = logging.getLogger(__name__)


def _delete_file_best_effort(field_file):
    """DB 삭제가 실제로 커밋된 뒤에 저장소의 파일을 지운다.

    커밋 이후로 미루는 것은, 삭제가 되돌려졌는데 파일만 사라져 남은 행이
    빈 곳을 가리키는 상황을 막기 위해서다. 저장소 오류는 기록만 하고 위로
    올리지 않는다 — 파일 정리 실패가 삭제 자체를 되돌리면 안 된다.
    """
    if not field_file:
        return
    name = field_file.name
    storage = field_file.storage

    def _delete():
        try:
            storage.delete(name)
        except Exception:
            logger.exception("Failed to delete file %s from storage", name)

    transaction.on_commit(_delete)


@receiver(post_delete, sender=VisitRecordPhoto)
def delete_visit_record_photo_file(sender, instance, **kwargs):
    _delete_file_best_effort(instance.image)


@receiver(post_delete, sender=PersonalEntry)
def delete_personal_entry_image_file(sender, instance, **kwargs):
    _delete_file_best_effort(instance.image)


@receiver(post_delete, sender=CollectionItem)
def delete_collection_item_image_file(sender, instance, **kwargs):
    _delete_file_best_effort(instance.image)
