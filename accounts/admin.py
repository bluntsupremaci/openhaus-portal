"""
Admin interface for OpenHaus accounts and system configuration.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.translation import gettext_lazy as _

from .models import CustomUser, GuestConfig, QuotaConfig, MembershipConfig


# ====================== CUSTOM USER ADMIN ======================
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser

    list_display = (
        "email",
        "full_name",
        "user_type",
        "university_id",
        "is_email_verified",
        "is_active",
        "is_staff",
        "date_joined",
    )

    list_filter = ("user_type", "is_email_verified", "is_active", "is_staff")
    search_fields = ("email", "university_id", "first_name", "last_name")
    readonly_fields = ("date_joined", "last_login", "updated_at")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Personal info"), {"fields": ("first_name", "last_name", "phone_number")}),
        (_("University info"), {"fields": ("user_type", "university_id")}),
        (_("Verification & Bonuses"), {
            "fields": ("is_email_verified", "email_verified_at", "signup_bonus_granted", "premium_trial_activated")
        }),
        (_("Permissions"), {
            "fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions"),
        }),
        (_("Important dates"), {"fields": ("last_login", "date_joined", "updated_at")}),
    )

    def full_name(self, obj):
        return obj.get_full_name() or obj.email
    

# ====================== GUEST CONFIG ======================
@admin.register(GuestConfig)
class GuestConfigAdmin(admin.ModelAdmin):
    list_display = ('name', 'mode', 'ad_enabled', 'reward_mb', 'daily_limit')
    fieldsets = (
        ("General", {"fields": ("name", "mode")}),
        ("Ad Reward", {"fields": ("ad_enabled", "reward_mb", "reward_minutes", "daily_limit", "expiry_hours")}),
    )
    class Media:
        js = ('admin/js/guest_config.js',)


@admin.register(QuotaConfig)
class QuotaConfigAdmin(admin.ModelAdmin):
    list_display = ('name', 'mode', 'default_daily_gb', 'non_student_gb')
    fieldsets = (
        ("General", {"fields": ("name", "mode")}),
        ("Data Quota Settings", {"fields": ("default_daily_gb", "non_student_gb", "speed_limit_mbps")}),
    )
    class Media:
        js = ('admin/js/quota_config.js',)


@admin.register(MembershipConfig)
class MembershipConfigAdmin(admin.ModelAdmin):
    list_display = ('name', 'mode', 'basic_daily_gb', 'premium_unlimited')
    fieldsets = (
        ("General", {"fields": ("name", "mode")}),
        ("Membership Rules", {"fields": ("basic_daily_gb", "premium_unlimited", "grace_period_days")}),
    )
    class Media:
        js = ('admin/js/membership_config.js',)