from django.contrib import admin

from drafts.models import DraftSource


@admin.register(DraftSource)
class DraftSourceAdmin(admin.ModelAdmin):
    pass
