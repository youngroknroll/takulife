from django.urls import path

from .runner_views import (
    RunnerCandidateSubmitView,
    RunnerClaimView,
    RunnerCompleteView,
    RunnerEventDraftSubmitView,
    RunnerHeartbeatView,
    RunnerKnownDraftUrlsView,
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
    path(
        "runs/<int:run_id>/drafts/",
        RunnerEventDraftSubmitView.as_view(),
        name="discovery-runner-event-drafts",
    ),
    path(
        "drafts/known/",
        RunnerKnownDraftUrlsView.as_view(),
        name="discovery-runner-known-drafts",
    ),
]
