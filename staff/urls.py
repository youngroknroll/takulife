"""스태프 콘솔(/staff/) URL 라우팅.

config/urls.py의 `include("staff.urls")`가 `/staff/` 전체를 이 파일에
넘긴다. 여기 없는 `/staff/...` 경로는 404가 된다.
"""
from django.urls import path
from django.views.generic import RedirectView

from . import views as staff_views

app_name = "staff"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="staff:dashboard"), name="root"),
    path("dashboard/", staff_views.dashboard, name="dashboard"),
    path(
        "draft-discovery/run/",
        staff_views.staff_draft_discovery_run,
        name="draft-discovery-run",
    ),
    path("drafts/", staff_views.event_drafts, name="draft-list"),
    path(
        "drafts/bulk-approve/",
        staff_views.StaffDraftBulkApproveView.as_view(),
        name="draft-bulk-approve",
    ),
    path("drafts/<int:draft_id>/", staff_views.event_draft_detail, name="draft-detail"),
    path(
        "drafts/<int:draft_id>/approve/",
        staff_views.StaffDraftApproveView.as_view(),
        name="draft-approve",
    ),
    path(
        "drafts/<int:draft_id>/reject/",
        staff_views.StaffDraftRejectView.as_view(),
        name="draft-reject",
    ),
    path("home-categories/", staff_views.staff_home_categories, name="home-categories"),
    path("events/", staff_views.staff_events, name="event-list"),
    path("events/new/", staff_views.staff_event_create, name="event-create"),
    path("events/<int:pk>/edit/", staff_views.staff_event_edit, name="event-edit"),
    path(
        "events/<int:pk>/toggle-publish/",
        staff_views.staff_event_toggle_publish,
        name="event-toggle-publish",
    ),
    path("events/<int:pk>/delete/", staff_views.staff_event_delete, name="event-delete"),
    path(
        "events/<int:pk>/verify/",
        staff_views.staff_event_verify,
        name="event-verify",
    ),
]
