# Data-only migration (collection domain design plan §3-4 (b), F-02).
#
# PR-C3's complete_visit_with_record() service now prevents new
# status/visit-record drift going forward, but pre-existing rows created
# before that guard could still disagree: a status row left at "planned" (or
# "missed") for a subject that already has at least one VisitRecord. This
# corrects that historical drift by transitioning those status rows to
# "visited" — the visit record's mere existence is stronger evidence than a
# stale "planned"/"missed" label.
#
# Reverse = RunPython.noop (approved 2026-07-15, PO sign-off): once corrected,
# a "visited" row created by this migration is indistinguishable from a
# "visited" row that was always correct — there is no marker recording which
# rows this migration touched, so restoring the pre-migration "planned"/
# "missed" value is not meaningfully reversible. This mirrors the same
# reverse=noop rationale already used in
# archive/migrations/0003_alter_usereventstatus_status_eventinterest.py.

from django.db import migrations


def fix_planned_status_with_existing_visit_record(apps, schema_editor):
    UserEventStatus = apps.get_model("archive", "UserEventStatus")
    VisitRecord = apps.get_model("archive", "VisitRecord")

    stale = UserEventStatus.objects.filter(status__in=["planned", "missed"])
    for status_row in stale.select_related("event", "personal_entry"):
        has_visit_record = VisitRecord.objects.filter(
            user_id=status_row.user_id,
            event_id=status_row.event_id,
            personal_entry_id=status_row.personal_entry_id,
        ).exists()
        if has_visit_record:
            UserEventStatus.objects.filter(pk=status_row.pk).update(status="visited")


class Migration(migrations.Migration):

    dependencies = [
        ("archive", "0015_alter_collectionitem_visit_record"),
    ]

    operations = [
        migrations.RunPython(
            fix_planned_status_with_existing_visit_record,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
