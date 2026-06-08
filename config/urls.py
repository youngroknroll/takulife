from django.contrib import admin
from django.urls import include, path

from core import views as core_views


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
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
    path("api/events/", include("events.urls")),
    path("api/event-drafts/", include("drafts.urls")),
    path("api/user-event-statuses/", include("archive.urls")),
]
