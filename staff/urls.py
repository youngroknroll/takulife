"""Staff Console URL routing (/staff/).

`path("staff/", include("staff.urls"))` consumes the entire `/staff/` prefix
in config/urls.py — every `/staff/...` route must live here, or it will
404 (no fallback to the top-level urlconf for this prefix).
"""
from django.urls import path
from django.views.generic import RedirectView

from core import views as core_views

from . import views as staff_views

app_name = "staff"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="staff:dashboard"), name="root"),
    path("dashboard/", staff_views.dashboard, name="dashboard"),
    path("drafts/", core_views.event_drafts, name="draft-list"),
    path("drafts/<int:draft_id>/", core_views.event_draft_detail, name="draft-detail"),
    path("home-categories/", core_views.staff_home_categories, name="home-categories"),
]
