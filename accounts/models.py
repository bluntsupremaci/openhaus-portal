"""
Custom User model for OpenHaus.
"""

import re
import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField


class CustomUserManager(BaseUserManager):
    def normalize_email(self, email: str | None) -> str | None:
        return super().normalize_email(email).lower() if email else None

    def create_user(self, email: str, password: str | None = None, **extra_fields):
        if not email:
            raise ValueError(_("The Email field must be set"))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_email_verified", True)
        extra_fields.setdefault("user_type", "staff")

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))

        return self.create_user(email, password, **extra_fields)


class CustomUser(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    email = models.EmailField(_("email address"), unique=True, db_index=True)
    username = models.CharField(_("username"), max_length=150, unique=True, blank=True, null=True)

    phone_number = PhoneNumberField(_("phone number"), unique=True, blank=True, null=True, region="NG")

    university_id = models.CharField(_("university ID"), max_length=50, blank=True, null=True, db_index=True)

    USER_TYPES = [
        ("student", _("Student")),
        ("staff", _("Staff")),
        ("guest", _("Guest")),
    ]

    user_type = models.CharField(max_length=20, choices=USER_TYPES, default="guest")

    is_email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)

    signup_bonus_granted = models.BooleanField(default=False)
    premium_trial_activated = models.BooleanField(default=False)
    premium_trial_end_date = models.DateTimeField(null=True, blank=True)

    one_time_quota_granted = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ["email"]

    def __str__(self) -> str:
        return self.get_full_name() or self.email

    def clean(self) -> None:
        super().clean()
        if self.is_superuser:
            return

    def save(self, *args, **kwargs) -> None:
        if self.email:
            self.email = self.email.lower().strip()
            if not self.username:
                self.username = self.email
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def is_university_member(self) -> bool:
        return self.user_type in ("student", "staff")


# ====================== STRUCTURED CONFIG MODELS ======================

class GuestConfig(models.Model):
    """Guest Access Configuration"""
    name = models.CharField(max_length=100, default="Default Guest Settings")

    mode = models.CharField(
        max_length=20,
        choices=[
            ('data_quota', 'Data Quota Based'),
            ('time_based', 'Time Based'),
            ('hybrid', 'Hybrid'),
        ],
        default='data_quota'
    )

    ad_enabled = models.BooleanField(default=True)
    reward_mb = models.PositiveIntegerField(default=500)
    reward_minutes = models.PositiveIntegerField(default=30)
    daily_limit = models.PositiveIntegerField(default=3)
    expiry_hours = models.PositiveIntegerField(default=24)

    class Meta:
        verbose_name = "Guest Access Configuration"
        verbose_name_plural = "Guest Access Configurations"

    def __str__(self):
        return self.name


class QuotaConfig(models.Model):
    """Data Quota System Configuration"""
    name = models.CharField(max_length=100, default="Default Quota Settings")

    mode = models.CharField(
        max_length=20,
        choices=[
            ('data_quota', 'Data Quota Based'),
            ('time_based', 'Time Based'),
            ('hybrid', 'Hybrid'),
        ],
        default='data_quota'
    )

    default_daily_gb = models.PositiveIntegerField(default=2)
    non_student_gb = models.PositiveIntegerField(default=5)
    speed_limit_mbps = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Data Quota Configuration"
        verbose_name_plural = "Data Quota Configurations"

    def __str__(self):
        return self.name


class MembershipConfig(models.Model):
    """Membership Plans Configuration"""
    name = models.CharField(max_length=100, default="Default Membership Settings")

    mode = models.CharField(
        max_length=20,
        choices=[
            ('data_quota', 'Data Quota Based'),
            ('time_based', 'Time Based'),
            ('hybrid', 'Hybrid'),
        ],
        default='data_quota'
    )

    basic_daily_gb = models.PositiveIntegerField(default=2)
    premium_unlimited = models.BooleanField(default=True)
    grace_period_days = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Membership Configuration"
        verbose_name_plural = "Membership Configurations"

    def __str__(self):
        return self.name


class GuestAdWatch(models.Model):
    """Track guest ad watches for rate limiting."""
    mac_address = models.CharField(max_length=17, db_index=True)
    watched_at = models.DateTimeField(auto_now_add=True)
    reward_granted = models.BooleanField(default=True)

    class Meta:
        ordering = ['-watched_at']
        verbose_name = "Guest Ad Watch"
        verbose_name_plural = "Guest Ad Watches"

    def __str__(self):
        return f"{self.mac_address} at {self.watched_at.date()}"