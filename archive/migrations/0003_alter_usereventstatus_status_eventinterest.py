# Manually ordered migration: CreateModel EventInterest → RunPython data migration
# → AlterField status choices.
#
# Operation order matters:
# 1. CreateModel first so the EventInterest table exists before data migration.
# 2. RunPython moves existing status="interested" rows into EventInterest,
#    then deletes those status rows.
# 3. AlterField removes "interested" from UserEventStatus.status choices
#    (Django choices are validated in Python, not enforced at DB level for
#    CharField, so this is a safe final step).
#
# RunPython reverse = noop: restoring interested rows risks UniqueConstraint
# collisions and is unsafe in a dev-only rollback scenario.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models, transaction


def migrate_interested_to_event_interest(apps, schema_editor):
    UserEventStatus = apps.get_model("archive", "UserEventStatus")
    EventInterest = apps.get_model("archive", "EventInterest")

    with transaction.atomic():
        for status_row in UserEventStatus.objects.filter(status="interested").select_related("user", "event"):
            existing = EventInterest.objects.filter(
                user=status_row.user, event=status_row.event
            ).first()
            if existing is None:
                interest = EventInterest.objects.create(
                    user=status_row.user,
                    event=status_row.event,
                )
                # auto_now_add ignores created_at on create(); update() bypasses it.
                EventInterest.objects.filter(pk=interest.pk).update(
                    created_at=status_row.created_at
                )
        UserEventStatus.objects.filter(status="interested").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("archive", "0002_visitrecord_visitrecordphoto"),
        ("events", "0002_remove_visitrecord_event_remove_visitrecord_user_and_more"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="EventInterest",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="archive_user_interests",
                        to="events.event",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="archive_event_interests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=("user", "event"),
                        name="unique_archive_user_event_interest",
                    )
                ],
            },
        ),
        migrations.RunPython(
            migrate_interested_to_event_interest,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="usereventstatus",
            name="status",
            field=models.CharField(
                choices=[
                    ("planned", "Planned"),
                    ("visited", "Visited"),
                    ("missed", "Missed"),
                ],
                max_length=20,
            ),
        ),
    ]
