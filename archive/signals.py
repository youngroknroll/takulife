import logging

from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import PersonalEntry, VisitRecordPhoto

logger = logging.getLogger(__name__)


def _delete_file_best_effort(field_file):
    """Best-effort delete a FieldFile's storage object once the deleting
    transaction actually commits.

    Deferred via transaction.on_commit so a rolled-back delete never loses a
    file the DB row still points at. Storage errors are logged, never
    propagated (mirrors events/services.py's poster cleanup pattern).
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
