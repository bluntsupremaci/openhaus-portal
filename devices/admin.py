"""
Admin interface for Device model.
"""

from django.contrib import admin

from .models import Device


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    """Admin configuration for user devices."""

    list_display = (
        "mac_address",
        "hostname",
        "user",
        "platform",
        "last_seen",
        "is_trusted",
        "is_blocked",
        "created_at",
    )

    list_filter = (
        "is_trusted",
        "is_blocked",
        "platform",
        "created_at",
    )

    search_fields = (
        "mac_address",
        "hostname",
        "user__email",
        "user__university_id",
    )

    readonly_fields = (
        "id",
        "last_seen",
        "created_at",
        "updated_at",
    )

    raw_id_fields = ("user",)

    ordering = ("-last_seen",)

    list_select_related = ("user",)

    def get_queryset(self, request):
        """Optimize queries by selecting related user."""
        return super().get_queryset(request).select_related("user")
