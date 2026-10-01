from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from access_policy.models import AccessGrant, AccessPolicySettings


@admin.register(AccessPolicySettings)
class AccessPolicySettingsAdmin(admin.ModelAdmin):
    fieldsets = (
        (
            _("How this works"),
            {
                "description": _(
                    "FAS order: active membership → valid free grant → deny. "
                    "Flow: signup window → verify (trial or hours) → daily free → ads → paid plan."
                ),
                "fields": (),
            },
        ),
        (
            _("1 · Signup (before verify)"),
            {
                "description": _("One-time try-the-network window."),
                "fields": (
                    "signup_temp_enabled",
                    "signup_temp_minutes",
                    "signup_temp_data_cap_mb",
                    "signup_timer_starts_on_first_fas",
                ),
            },
        ),
        (
            _("2 · After email verification (once)"),
            {
                "description": _("Runs once when email is verified."),
                "fields": (
                    "verify_student_trial_days",
                    "verify_student_trial_plan_slug",
                    "verify_non_student_hours",
                    "student_email_domains",
                ),
            },
        ),
        (
            _("3 · Daily free (verified, no plan)"),
            {
                "description": _("Resets each calendar day. Not for active members."),
                "fields": (
                    "daily_free_enabled",
                    "daily_free_student_minutes",
                    "daily_free_non_student_minutes",
                    "timezone_name",
                ),
            },
        ),
        (
            _("4 · Ad rewards"),
            {
                "description": _("Guests and verified users without a plan."),
                "fields": (
                    "ad_reward_enabled",
                    "ad_reward_minutes",
                    "ad_reward_data_cap_mb",
                    "ad_daily_limit",
                    "ad_grant_expiry_hours",
                ),
            },
        ),
        (_("Meta"), {"fields": ("updated_at",)}),
    )
    readonly_fields = ("updated_at",)

    def has_add_permission(self, request):
        return not AccessPolicySettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AccessGrant)
class AccessGrantAdmin(admin.ModelAdmin):
    list_display = (
        "id", "user", "grant_type", "starts_at", "expires_at",
        "duration_seconds", "seconds_used", "is_active", "grant_day",
    )
    list_filter = ("grant_type", "is_active")
    search_fields = ("user__email", "notes")
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("user",)
