from django.urls import path

from .runner_views import (
    RunnerCandidateSubmitView,
    RunnerClaimView,
    RunnerCompleteView,
    RunnerHeartbeatView,
)


urlpatterns = [
    path("heartbeat/", RunnerHeartbeatView.as_view(), name="discovery-runner-heartbeat"),
    path("claim/", RunnerClaimView.as_view(), name="discovery-runner-claim"),
    path(
        "runs/<int:run_id>/candidates/",
        RunnerCandidateSubmitView.as_view(),
        name="discovery-runner-candidates",
    ),
    path(
        "runs/<int:run_id>/complete/",
        RunnerCompleteView.as_view(),
        name="discovery-runner-complete",
    ),
]
