from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self):
        # 시그널 수신기를 등록하는 부수효과 임포트
        from accounts import signals  # noqa: F401
