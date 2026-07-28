"""
Admin interface for Quota models.
"""

from django.contrib import admin

from .models import QuotaAllocation, QuotaUsage


@admin.register(QuotaAllocation)
class QuotaAllocationAdmin(admin.ModelAdmin):
    """Admin interface for quota allocations."""

    list_display = (
        "user",
        "quota_type",
        "total_bytes_display",
        "remaining_bytes_display",
        "consumed_bytes_display",
        "is_active",
        "expires_at",
    )

    list_filter = (
        "quota_type",
        "is_active",
        "expires_at",
        "created_at",
    )

    search_fields = (
        "user__email",
        "user__university_id",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "granted_at",
        "consumed_bytes_display",
    )

    raw_id_fields = ("user",)  # Removed device if it's commented out in model

    fieldsets = (
        (
            "Allocation",
            {
                "fields": (
                    "id",
                    "user",
                    "quota_type",
                )
            },
        ),
        (
            "Quota",
            {
                "fields": (
                    "total_bytes",
                    "used_bytes",
                    "remaining_bytes_display",
                    "consumed_bytes_display",
                    "is_active",
                )
            },
        ),
        (
            "Lifecycle",
            {
                "fields": (
                    "granted_at",
                    "expires_at",
                    "created_at",
                    "updated_at",
                )
            },
        ),
        (
            "Additional Information",
            {
                "fields": ("notes",),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="Total")
    def total_bytes_display(self, obj):
        return f"{obj.total_bytes:,} bytes"

    @admin.display(description="Remaining")
    def remaining_bytes_display(self, obj):
        return f"{obj.remaining_bytes:,} bytes"

    @admin.display(description="Consumed")
    def consumed_bytes_display(self, obj):
        return f"{obj.consumed_bytes:,} bytes"


@admin.register(QuotaUsage)
class QuotaUsageAdmin(admin.ModelAdmin):
    """Admin interface for quota usage records (immutable audit log)."""

    list_display = (
        "user",
        "quota_type",
        "bytes_used_display",
        "recorded_at",
    )

    list_filter = (
        "allocation__quota_type",
        "recorded_at",
    )

    search_fields = (
        "allocation__user__email",
        "allocation__user__university_id",
    )

    ordering = ("-recorded_at",)

    readonly_fields = (
        "id",
        "allocation",
        "bytes_used",
        "metadata",
        "recorded_at",
    )

    def has_add_permission(self, request):
        """Usage records are created only by the service layer."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Preserve immutable audit trail."""
        return False

    @admin.display(description="User")
    def user(self, obj):
        return obj.allocation.user.email

    @admin.display(description="Quota Type")
    def quota_type(self, obj):
        return obj.allocation.get_quota_type_display()

    @admin.display(description="Bytes Used")
    def bytes_used_display(self, obj):
        return f"{obj.bytes_used:,} bytes"
