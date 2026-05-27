from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("core.urls")),
    path("api/events/", include("events.urls")),
    path("api/me/", include("events.status_urls")),
    path("api/admin/", include("drafts.urls")),
]
