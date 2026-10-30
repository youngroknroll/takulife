from django.urls import path

from events.runner_views import TranslationPendingView, TranslationSubmitView

urlpatterns = [
    path("pending/", TranslationPendingView.as_view(), name="translation-runner-pending"),
    path("submit/", TranslationSubmitView.as_view(), name="translation-runner-submit"),
]
