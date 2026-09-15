from django.apps import AppConfig


class EventsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "events"

    def ready(self):
        # 카테고리 비활성화 시 팔레트 슬롯 반납 신호 구독을 등록한다.
        from . import signals  # noqa: F401
