"""PR-0e checkpoint A2: create the DatabaseCache table (G11).

config/settings.py CACHES["default"] points at a "django_cache" table that
`createcachetable` normally provisions as a separate manual step. Wrapping it
in a migration means `manage.py migrate` alone (the only step the deploy
entrypoint/CI run) is enough — no extra deploy-time command to remember.
Django's own test-database creation already provisions this table
automatically for every test run (independent of this migration), so this
migration only matters for real (dev/staging/production) databases.
"""
from django.core.management import call_command
from django.db import migrations


CACHE_TABLE_NAME = "django_cache"


def create_cache_table(apps, schema_editor):
    call_command("createcachetable", CACHE_TABLE_NAME, verbosity=0)


def drop_cache_table(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(f"DROP TABLE IF EXISTS {CACHE_TABLE_NAME}")


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_cache_table, drop_cache_table),
    ]
