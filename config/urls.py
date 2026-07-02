from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

from core import views as core_views
from core.promotion_views import PromotePersonalEntryView


urlpatterns = [
    path("", core_views.home, name="home"),
    path("events/", core_views.event_list, name="event-list-page"),
    path("events/<int:event_id>/", core_views.event_detail, name="event-detail-page"),
    path("archive/", core_views.archive, name="archive-page"),
    path(
        "archive/statuses/",
        core_views.archive_statuses,
        name="archive-statuses-page",
    ),
    path(
        "archive/visits/new/",
        core_views.archive_visit_create,
        name="archive-visit-create-page",
    ),
    path(
        "archive/visits/<int:record_id>/edit/",
        core_views.archive_visit_edit,
        name="archive-visit-edit-page",
    ),
    path("archive/visits/", core_views.archive_visits, name="archive-visits-page"),
    path(
        "archive/items/",
        core_views.archive_personal_entries,
        name="archive-personal-entries-page",
    ),
    path("archive/interests/", core_views.archive_interests, name="archive-interests"),
    # Old draft-review URLs, relocated under the Staff Console (/staff/drafts/…).
    # Non-permanent 302s (browsers/bookmarks may still hold the old links) that
    # preserve any ?next= query string.
    path(
        "event-drafts/",
        RedirectView.as_view(url="/staff/drafts/", query_string=True, permanent=False),
        name="event-drafts-page",
    ),
    path(
        "event-drafts/<int:draft_id>/",
        RedirectView.as_view(
            url="/staff/drafts/%(draft_id)s/", query_string=True, permanent=False
        ),
        name="event-draft-detail-page",
    ),
    path("staff/", include("staff.urls")),
    path("accounts/", include("allauth.urls")),
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
    path("api/events/", include("events.urls")),
    path("api/event-drafts/", include("drafts.urls")),
    path("api/user-event-statuses/", include("archive.urls")),
    path("api/visit-records/", include("archive.visit_urls")),
    path("api/event-interests/", include("archive.interest_urls")),
    path(
        "api/personal-entries/<int:pk>/promote/",
        PromotePersonalEntryView.as_view(),
        name="personal-entry-promote",
    ),
    path("api/personal-entries/", include("archive.personal_urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
