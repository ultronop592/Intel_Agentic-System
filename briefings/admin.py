from django.contrib import admin

from briefings.models import Briefing


@admin.register(Briefing)
class BriefingAdmin(admin.ModelAdmin):
    list_display = ("competitor", "user", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("competitor__name", "user__username", "content")
