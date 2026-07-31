from django.contrib import admin

from .models import StaffActionLog


@admin.register(StaffActionLog)
class StaffActionLogAdmin(admin.ModelAdmin):
    """감사 로그는 조회만 가능하다.

    추가/수정/삭제는 항상 막는다 — 로그는 스태프 뷰 쪽에서만 만들어지고
    관리자 화면에서 직접 만들거나 고칠 수는 없다.
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
