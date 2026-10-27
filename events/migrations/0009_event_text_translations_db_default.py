# Django의 AddField는 열을 채운 뒤 DB 기본값을 지운다. 열을 모르는 구 코드의 INSERT가
# 배포 교체 구간이나 코드 롤백 때 NOT NULL 위반이 나지 않도록 DB 기본값을 되살린다.
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("events", "0008_event_text_translations")]

    operations = [
        migrations.RunSQL(
            sql="ALTER TABLE events_event ALTER COLUMN text_translations SET DEFAULT '{}'::jsonb",
            reverse_sql="ALTER TABLE events_event ALTER COLUMN text_translations DROP DEFAULT",
        ),
    ]
