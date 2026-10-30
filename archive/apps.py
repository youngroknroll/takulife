from django.apps import AppConfig


class ArchiveConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "archive"

    def ready(self):
        # 시그널 수신기를 등록하는 부수효과 임포트
        from archive import signals  # noqa: F401
