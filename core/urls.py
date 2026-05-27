from django.urls import path

from . import auth_views, views


app_name = "core"

urlpatterns = [
    path("", views.api_root, name="api-root"),
    path("health/", views.health, name="health"),
    path("auth/me/", auth_views.me, name="auth-me"),
]
