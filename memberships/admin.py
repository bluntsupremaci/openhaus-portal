from django.contrib import admin
from django.utils import timezone

from .models import (
    MembershipPlan,
    MembershipStatus,
    UserMembership,
)


@admin.register(MembershipPlan)
class MembershipPlanAdmin(admin.ModelAdmin):
    """Admin interface for membership plans."""

    list_display = (
        "name",
        "price",
        "currency",
        "duration_days",
        "included_quota_gb",
        "max_devices",
        "speed_limit_mbps",
        "is_active",
    )

    list_filter = (
        "is_active",
        "currency",
    )

    search_fields = (
        "name",
        "slug",
        "description",
    )

    ordering = (
        "price",
        "duration_days",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
    )

    prepopulated_fields = {
        "slug": ("name",),
    }

    fieldsets = (
        (
            "Plan Information",
            {
                "fields": (
                    "id",
                    "name",
                    "slug",
                    "description",
                )
            },
        ),
        (
            "Pricing",
            {
                "fields": (
                    "price",
                    "currency",
                    "duration_days",
                )
            },
        ),
        (
            "Limits",
            {
                "fields": (
                    "included_quota_gb",
                    "max_devices",
                    "speed_limit_mbps",
                )
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "is_active",
                )
            },
        ),
        (
            "Audit",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )


@admin.register(UserMembership)
class UserMembershipAdmin(admin.ModelAdmin):
    """Admin interface for user memberships."""

    list_display = (
        "user",
        "plan",
        "status",
        "remaining_days",
        "start_date",
        "end_date",
    )

    list_filter = (
        "status",
        "plan",
    )

    search_fields = (
        "user__email",
        "user__first_name",
        "user__last_name",
        "user__university_id",
        "plan__name",
    )

    ordering = (
        "-end_date",
    )

    readonly_fields = (
        "id",
        "created_at",
        "updated_at",
        "remaining_days",
        "remaining_seconds",
        "has_expired",
        "is_valid",
    )

    raw_id_fields = (
        "user",
    )

    autocomplete_fields = (
        "plan",
    )

    list_select_related = (
        "user",
        "plan",
    )

    fieldsets = (
        (
            "Membership",
            {
                "fields": (
                    "id",
                    "user",
                    "plan",
                    "status",
                )
            },
        ),
        (
            "Validity",
            {
                "fields": (
                    "start_date",
                    "end_date",
                )
            },
        ),
        (
            "Status",
            {
                "fields": (
                    "is_valid",
                    "has_expired",
                    "remaining_days",
                    "remaining_seconds",
                )
            },
        ),
        (
            "Audit",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )

    def remaining_days(self, obj):
        """Display remaining membership days."""
        return obj.remaining_days

    remaining_days.short_description = "Days Left"

    def remaining_seconds(self, obj):
        """Display remaining membership seconds."""
        return obj.remaining_seconds

    remaining_seconds.short_description = "Seconds Left"

    def has_expired(self, obj):
        """Display expiration state."""
        return obj.end_date <= timezone.now()

    has_expired.boolean = True
    has_expired.short_description = "Expired"

    def is_valid(self, obj):
        """Display validity state."""
        return (
            obj.status == MembershipStatus.ACTIVE
            and obj.end_date > timezone.now()
        )

    is_valid.boolean = True
    is_valid.short_description = "Valid"