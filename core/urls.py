from django.urls import path

from . import auth_views, views
from .client_error_views import ClientErrorReportView


app_name = "core"

urlpatterns = [
    path("", views.api_root, name="api-root"),
    path("health/", views.health, name="health"),
    path("auth/me/", auth_views.me, name="auth-me"),
    path("client-errors/", ClientErrorReportView.as_view(), name="client-error-report"),
]
