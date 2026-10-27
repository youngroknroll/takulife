from django.urls import path

from .runner_views import TranslationPendingView, TranslationSubmitView


urlpatterns = [
    path("pending/", TranslationPendingView.as_view(), name="translation-runner-pending"),
    path("submit/", TranslationSubmitView.as_view(), name="translation-runner-submit"),
]
