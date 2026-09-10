from django.db import migrations, models
from django.db.models.functions import Lower

import accounts.validators


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
        migrations.AddConstraint(
            model_name="user",
            constraint=models.UniqueConstraint(
                Lower("nickname"), name="accounts_user_nickname_ci_unique"
            ),
        ),
    ]
