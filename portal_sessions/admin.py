"""
Admin interface for WiFiSession model.
"""

from django.contrib import admin

from .models import WiFiSession


@admin.register(WiFiSession)
class WiFiSessionAdmin(admin.ModelAdmin):
    """Admin configuration for WiFi sessions."""

    list_display = (
        "user",
        "device",
        "mac_address",
        "ip_address",
        "started_at",  # ← updated
        "ended_at",  # ← updated
        "bytes_used",  # ← updated
        "is_active",
    )

    list_filter = (
        "is_active",
        "started_at",
        "ended_at",
    )

    search_fields = (
        "user__email",
        "user__university_id",
        "mac_address",
        "ip_address",
    )

    readonly_fields = (
        "id",
        "started_at",
        "ended_at",
        "duration_seconds",
        "bytes_used",
    )

    raw_id_fields = ("user", "device")

    ordering = ("-started_at",)

    list_select_related = ("user", "device")
