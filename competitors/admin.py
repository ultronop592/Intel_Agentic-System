from django.contrib import admin

from competitors.models import Competitor, CompetitorSnapshot


@admin.register(Competitor)
class CompetitorAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "url", "is_active", "last_status", "last_scraped", "created_at")
    list_filter = ("is_active", "last_status", "created_at")
    search_fields = ("name", "url", "user__username")


@admin.register(CompetitorSnapshot)
class CompetitorSnapshotAdmin(admin.ModelAdmin):
    list_display = ("competitor", "content_hash", "scraped_at")
    search_fields = ("competitor__name", "content_hash")
    readonly_fields = ("scraped_at",)
