"""Admin for accounts app."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from accounts.models import CustomUser, GuestAdWatch


@admin.register(CustomUser)
class CustomUserAdmin(BaseUserAdmin):
    ordering = ("email",)
    list_display = (
        "email",
        "user_type",
        "is_email_verified",
        "is_active",
        "is_staff",
        "signup_temp_access_granted",
        "signup_bonus_granted",
        "premium_trial_activated",
    )
    list_filter = (
        "user_type",
        "is_email_verified",
        "is_active",
        "is_staff",
        "signup_bonus_granted",
    )
    search_fields = ("email", "first_name", "last_name", "university_id")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (
            "Profile",
            {
                "fields": (
                    "first_name",
                    "last_name",
                    "phone_number",
                    "user_type",
                    "university_id",
                )
            },
        ),
        (
            "Verification & access flags",
            {
                "fields": (
                    "is_email_verified",
                    "email_verified_at",
                    "signup_temp_access_granted",
                    "signup_temp_pending",
                    "signup_bonus_granted",
                    "premium_trial_activated",
                    "premium_trial_end_date",
                    "one_time_quota_granted",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Dates", {"fields": ("last_login", "date_joined", "updated_at")}),
    )
    readonly_fields = ("updated_at", "last_login", "date_joined")

    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "password1",
                    "password2",
                    "user_type",
                    "is_staff",
                    "is_superuser",
                ),
            },
        ),
    )

    filter_horizontal = ("groups", "user_permissions")


@admin.register(GuestAdWatch)
class GuestAdWatchAdmin(admin.ModelAdmin):
    list_display = ("mac_address", "watched_at", "reward_granted")
    list_filter = ("reward_granted",)
    search_fields = ("mac_address",)
    readonly_fields = ("watched_at",)
