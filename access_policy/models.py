"""Admin-configurable free-access policy and time grants."""

from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class AccessPolicySettings(models.Model):
    """
    One row. Admin → Access policy settings.
    FAS: active membership first, then these grants.
    """

    signup_temp_enabled = models.BooleanField(
        default=True,
        verbose_name=_("Signup free access"),
        help_text=_("New accounts get one short free window before verify."),
    )
    signup_temp_minutes = models.PositiveIntegerField(
        default=30,
        verbose_name=_("Signup minutes"),
        help_text=_("Length of that one-time window."),
    )
    signup_temp_data_cap_mb = models.PositiveIntegerField(
        default=200,
        verbose_name=_("Signup data cap (MB)"),
        help_text=_("Max data in signup window. 0 = no cap."),
    )
    signup_timer_starts_on_first_fas = models.BooleanField(
        default=True,
        verbose_name=_("Start signup timer on first connect"),
        help_text=_("On: clock starts at first Wi‑Fi allow. Off: at signup."),
    )

    verify_student_trial_days = models.PositiveIntegerField(
        default=30,
        verbose_name=_("Student trial (days)"),
        help_text=_("After verify: one free membership for students/staff."),
    )
    verify_student_trial_plan_slug = models.SlugField(
        default="premium-trial",
        verbose_name=_("Student trial plan slug"),
        help_text=_("MembershipPlan.slug to use (create plan in Admin if missing)."),
    )
    verify_non_student_hours = models.PositiveIntegerField(
        default=24,
        verbose_name=_("Non-student free hours"),
        help_text=_("After verify: one free time window for non-students."),
    )

    daily_free_enabled = models.BooleanField(
        default=True,
        verbose_name=_("Daily free access"),
        help_text=_("Verified users with no membership get free minutes each day."),
    )
    daily_free_student_minutes = models.PositiveIntegerField(
        default=60,
        verbose_name=_("Daily minutes (student)"),
        help_text=_("Per day for verified student/staff without a plan."),
    )
    daily_free_non_student_minutes = models.PositiveIntegerField(
        default=30,
        verbose_name=_("Daily minutes (non-student)"),
        help_text=_("Per day for verified non-student without a plan."),
    )
    timezone_name = models.CharField(
        max_length=64,
        default="Africa/Lagos",
        verbose_name=_("Daily reset timezone"),
        help_text=_("Day boundary for daily free and ad limits."),
    )

    ad_reward_enabled = models.BooleanField(
        default=True,
        verbose_name=_("Ad rewards"),
        help_text=_("Guests and verified non-members can earn time via ads."),
    )
    ad_reward_minutes = models.PositiveIntegerField(
        default=20,
        verbose_name=_("Minutes per ad"),
        help_text=_("Access time after one completed ad."),
    )
    ad_reward_data_cap_mb = models.PositiveIntegerField(
        default=100,
        verbose_name=_("Ad data cap (MB)"),
        help_text=_("Optional data limit on an ad grant. 0 = time only."),
    )
    ad_daily_limit = models.PositiveSmallIntegerField(
        default=3,
        verbose_name=_("Ads per day"),
        help_text=_("Max ad rewards per user per calendar day."),
    )
    ad_grant_expiry_hours = models.PositiveIntegerField(
        default=4,
        verbose_name=_("Ad grant valid for (hours)"),
        help_text=_("Unused ad time expires after this many hours."),
    )

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Access policy settings")
        verbose_name_plural = _("Access policy settings")

    def __str__(self) -> str:
        return "Access policy settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        return

    @classmethod
    def get_solo(cls) -> AccessPolicySettings:
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class AccessGrantType(models.TextChoices):
    SIGNUP_TEMP = "SIGNUP_TEMP", _("Signup")
    VERIFY_BONUS = "VERIFY_BONUS", _("Verify bonus")
    DAILY_FREE = "DAILY_FREE", _("Daily free")
    AD_REWARD = "AD_REWARD", _("Ad reward")
    MANUAL = "MANUAL", _("Manual")


class AccessGrant(models.Model):
    """Free time window. Used when user has no active membership."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="access_grants",
        help_text=_("Account that may use this window."),
    )
    grant_type = models.CharField(
        max_length=32,
        choices=AccessGrantType.choices,
        db_index=True,
        help_text=_("Why this window was given."),
    )
    starts_at = models.DateTimeField(default=timezone.now, help_text=_("Window opens."))
    expires_at = models.DateTimeField(db_index=True, help_text=_("Hard end (wall clock)."))
    duration_seconds = models.PositiveIntegerField(
        help_text=_("Max online seconds inside the window."),
    )
    seconds_used = models.PositiveIntegerField(default=0, help_text=_("Seconds consumed."))
    data_cap_bytes = models.BigIntegerField(
        default=0, help_text=_("Max bytes in window. 0 = no cap.")
    )
    bytes_used = models.BigIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True, help_text=_("Off = ignored."))
    grant_day = models.DateField(
        null=True, blank=True, db_index=True, help_text=_("Local day for daily/ad caps.")
    )
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Access grant")
        verbose_name_plural = _("Access grants")
        ordering = ["-expires_at"]
        indexes = [
            models.Index(fields=["user", "is_active", "expires_at"]),
            models.Index(fields=["user", "grant_type", "grant_day"]),
        ]

    def __str__(self) -> str:
        return f"{self.user_id} · {self.grant_type} · {self.expires_at:%Y-%m-%d %H:%M}"

    @property
    def remaining_seconds(self) -> int:
        if not self.is_active:
            return 0
        now = timezone.now()
        if now >= self.expires_at:
            return 0
        wall = int((self.expires_at - now).total_seconds())
        quota = max(0, int(self.duration_seconds) - int(self.seconds_used))
        return max(0, min(wall, quota))

    @property
    def is_currently_valid(self) -> bool:
        return self.remaining_seconds > 0

    def clean(self):
        if self.expires_at <= self.starts_at:
            raise ValidationError(_("expires_at must be after starts_at."))
