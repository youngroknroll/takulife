from django.contrib import admin

from .models import StaffActionLog


@admin.register(StaffActionLog)
class StaffActionLogAdmin(admin.ModelAdmin):
    """Superuser-only read access to the staff audit trail.

    Append-only: add/change/delete are always disallowed here, regardless of
    permission level — log entries are only ever created by the staff view
    boundary (see PR-2 sub-step D), never through the admin UI.
    """

    list_display = ["created_at", "action", "actor", "target_draft"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_module_permission(self, request):
        return request.user.is_superuser
