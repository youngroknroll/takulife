from django.db import migrations, models
from django.db.models.functions import Lower

import accounts.validators


# 백필 값은 회원<pk>로 결정적이다(§B). reverse는 noop이다 — 백필로 채운
# 값과 그 뒤 실사용자가 고른 값을 구분할 표식이 없어 되돌릴 수 없다.
def backfill_nickname(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    for user in User.objects.filter(models.Q(nickname__isnull=True) | models.Q(nickname="")):
        user.nickname = f"회원{user.pk}"
        user.save(update_fields=["nickname"])


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_user_password_changed_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="nickname",
            field=models.CharField(
                max_length=20,
                null=True,
                validators=[accounts.validators.validate_nickname],
            ),
        ),
        migrations.RunPython(backfill_nickname, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                Lower("nickname"), name="accounts_user_nickname_ci_unique"
            ),
        ),
    ]
