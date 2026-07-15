# Data + state migration (collection domain design plan §3-5 M2, PR-C4 stage
# E). Every GOODS PersonalEntry has already been copied to CollectionItem by
# 0017 (reconciled against the dev DB — 1 GOODS row -> 1 CollectionItem row,
# 2026-07-15/16 PO sign-off) — this migration deletes the now-redundant
# original GOODS rows and removes "goods" from the kind field's choices.
# PLACE rows are never touched (the filter is kind="goods" only).
#
# Reverse = RunPython.noop (approved 2026-07-16, PO sign-off, mirrors the
# same rationale already used in
# archive/migrations/0003_alter_usereventstatus_status_eventinterest.py and
# archive/migrations/0016_fix_planned_status_with_existing_visit_record.py):
# restoring a deleted GOODS row loses no longer-recoverable information (the
# 0017 CollectionItem copy is the durable record going forward), and this is
# a dev-only rollback scenario with zero real users at the time of writing.
#
# This noop is also what closes 0017's reversibility window (gate follow-up
# M1, see 0017's docstring for the full explanation): once this migration
# has run, `migrate archive 0016` no longer restores GOODS rows, so 0017's
# reverse finds nothing left to match and deletes no CollectionItem copies
# either. That is the approved design (plan §3-5) — applying 0018 is the
# deliberate end of the rollback window, not an accidental side effect.

from django.db import migrations, models


def delete_goods_personal_entries(apps, schema_editor):
    PersonalEntry = apps.get_model("archive", "PersonalEntry")
    PersonalEntry.objects.filter(kind="goods").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("archive", "0017_migrate_goods_to_collection_items"),
    ]

    operations = [
        migrations.RunPython(
            delete_goods_personal_entries,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="personalentry",
            name="kind",
            field=models.CharField(choices=[("place", "Place")], max_length=20),
        ),
    ]
