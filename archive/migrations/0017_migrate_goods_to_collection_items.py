# Data-only migration (collection domain design plan §3-5, PR-C4 stage C).
#
# Copies every GOODS PersonalEntry (dev-only, pre-production data — see the
# plan's §2 survey) into the new CollectionItem domain. The approved field
# mapping is fixed and deliberately narrow (§3-5): title -> name, work_title,
# memo, location_name -> acquisition_source, category -> item_type (matched
# against a frozen snapshot of core.vocab.COLLECTION_ITEM_TYPE as of
# 2026-07-15, else "etc"), quantity=1, tradeable_quantity=0, is_wanted=False,
# visibility="private", event=None, visit_record=None, acquired_on=None
# (never guessed from created_at).
#
# The vocab snapshot below is copied, not imported from core.vocab — a data
# migration must stay runnable when `manage.py migrate` replays the entire
# history against a fresh DB (new dev clone, CI test DB creation), and an app
# module can be renamed or restructured long after this migration is
# written. Importing it here would let a future, unrelated core.vocab change
# break migration application for everyone (approved 2026-07-16, PO
# sign-off).
#
# Defensive failure ("no silent data loss", AGENTS.md): the entire run aborts
# with a clear per-row message — no partial commit — if any GOODS row is
# referenced by a VisitRecord/EventInterest/UserEventStatus (needs a manual
# decision, not an automatic one), carries a non-empty url/region (fields
# CollectionItem has no home for), or has a non-NONE promotion_status.
#
# CP-Image: the migrated CollectionItem gets its own physically independent
# file under its own upload_to ("collection-items/") — never the same
# storage key as the source PersonalEntry.image. archive/signals.py deletes
# a PersonalEntry's image file from storage on post_delete; sharing a
# storage key would silently wipe the migrated copy's photo the moment the
# original GOODS row is deleted (this migration does not delete it — that is
# a separate, later migration).
#
# Reverse: deletes only the copies this run created (matched by exact field
# equality against each remaining GOODS PersonalEntry's mapped values — the
# approved field list has no provenance/link field, so this is the only
# available correlation short of adding a schema field the plan didn't
# approve). Unrelated pre-existing CollectionItem rows and the original
# PersonalEntry rows are never touched by either direction.

from django.core.files.base import ContentFile
from django.db import migrations, transaction

# Frozen snapshot of core.vocab.COLLECTION_ITEM_TYPE as of 2026-07-15 — see
# the module docstring above for why this is copied, not imported.
_COLLECTION_ITEM_TYPE = (
    ("acrylic_stand", "아크릴 스탠드"),
    ("keyring", "키링"),
    ("badge", "뱃지"),
    ("photocard", "포토카드"),
    ("plush", "인형"),
    ("stationery", "문구"),
    ("etc", "기타"),
)

_ITEM_TYPE_SLUGS = {slug for slug, _ in _COLLECTION_ITEM_TYPE}
_ITEM_TYPE_LABEL_TO_SLUG = {label: slug for slug, label in _COLLECTION_ITEM_TYPE}


class GoodsMigrationBlocked(Exception):
    """A GOODS PersonalEntry row can't be safely auto-migrated and needs a
    manual decision (collection domain design plan §3-5)."""


def _map_item_type(category: str) -> str:
    if category in _ITEM_TYPE_SLUGS:
        return category
    return _ITEM_TYPE_LABEL_TO_SLUG.get(category, "etc")


def _mapped_fields(entry):
    """The deterministic CollectionItem field values for a GOODS PersonalEntry
    — shared by the forward create and the reverse match-and-delete so the
    two directions can never disagree about what "this migration's copy"
    looks like."""
    return {
        "name": entry.title,
        "work_title": entry.work_title,
        "item_type": _map_item_type(entry.category),
        "quantity": 1,
        "acquired_on": None,
        "acquisition_source": entry.location_name,
        "event": None,
        "visit_record": None,
        "memo": entry.memo,
        "is_wanted": False,
        "tradeable_quantity": 0,
        "visibility": "private",
    }


def _copy_image(entry, item):
    if not entry.image:
        return
    filename = entry.image.name.rsplit("/", 1)[-1]
    content = entry.image.read()
    entry.image.close()
    # FieldFile.save() routes through CollectionItem.image's own upload_to
    # ("collection-items/") and the storage backend's collision-avoiding
    # naming — the result is a new, physically independent file, never the
    # same storage key as entry.image (CP-Image).
    item.image.save(filename, ContentFile(content), save=True)


def migrate_goods_to_collection_items(apps, schema_editor):
    PersonalEntry = apps.get_model("archive", "PersonalEntry")
    CollectionItem = apps.get_model("archive", "CollectionItem")
    VisitRecord = apps.get_model("archive", "VisitRecord")
    EventInterest = apps.get_model("archive", "EventInterest")
    UserEventStatus = apps.get_model("archive", "UserEventStatus")

    goods_entries = list(PersonalEntry.objects.filter(kind="goods"))
    if not goods_entries:
        return

    errors = []
    for entry in goods_entries:
        for label, queryset in (
            ("VisitRecord", VisitRecord.objects.filter(personal_entry_id=entry.id)),
            ("EventInterest", EventInterest.objects.filter(personal_entry_id=entry.id)),
            ("UserEventStatus", UserEventStatus.objects.filter(personal_entry_id=entry.id)),
        ):
            ids = list(queryset.values_list("id", flat=True))
            if ids:
                errors.append(
                    f"PersonalEntry(id={entry.id}) is referenced by "
                    f"{label}(id={ids}) — manual decision required, not migrated."
                )
        if entry.url:
            errors.append(
                f"PersonalEntry(id={entry.id}) has a non-empty url "
                "— CollectionItem has no matching field."
            )
        if entry.region:
            errors.append(
                f"PersonalEntry(id={entry.id}) has a non-empty region "
                "— CollectionItem has no matching field."
            )
        if entry.promotion_status:
            errors.append(
                f"PersonalEntry(id={entry.id}) has promotion_status="
                f"{entry.promotion_status!r} — not migratable."
            )

    if errors:
        raise GoodsMigrationBlocked("; ".join(errors))

    with transaction.atomic():
        for entry in goods_entries:
            item = CollectionItem.objects.create(user_id=entry.user_id, **_mapped_fields(entry))
            _copy_image(entry, item)


def delete_migrated_collection_items(apps, schema_editor):
    PersonalEntry = apps.get_model("archive", "PersonalEntry")
    CollectionItem = apps.get_model("archive", "CollectionItem")

    for entry in PersonalEntry.objects.filter(kind="goods"):
        CollectionItem.objects.filter(user_id=entry.user_id, **_mapped_fields(entry)).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("archive", "0016_fix_planned_status_with_existing_visit_record"),
    ]

    operations = [
        migrations.RunPython(
            migrate_goods_to_collection_items,
            reverse_code=delete_migrated_collection_items,
        ),
    ]
