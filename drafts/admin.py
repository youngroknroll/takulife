from django.contrib import admin

from .models import DraftSource


@admin.register(DraftSource)
class DraftSourceAdmin(admin.ModelAdmin):
    pass
