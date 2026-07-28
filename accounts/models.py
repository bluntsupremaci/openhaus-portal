"""Custom User model for OpenHaus."""

from __future__ import annotations

import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField


class CustomUserManager(BaseUserManager):
    @classmethod
    def normalize_email(cls, email: str | None) -> str:
        email = (email or "").strip().lower()
        return super().normalize_email(email) if email else ""

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
    username = models.CharField(
        _("username"), max_length=150, unique=True, blank=True, null=True
    )
    phone_number = PhoneNumberField(
        _("phone number"), unique=True, blank=True, null=True, region="NG"
    )
    university_id = models.CharField(
        _("university ID"), max_length=50, blank=True, null=True, db_index=True
    )
    USER_TYPES = [
        ("student", _("Student")),
        ("staff", _("Staff")),
        ("guest", _("Guest")),
    ]
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default="guest")

    is_email_verified = models.BooleanField(default=False)
    email_verified_at = models.DateTimeField(null=True, blank=True)

    # Access policy flags (one-time)
    signup_temp_access_granted = models.BooleanField(
        default=False,
        help_text=_("Signup free window already used or reserved."),
    )
    signup_temp_pending = models.BooleanField(
        default=False,
        help_text=_("Entitled; timer starts on first Wi‑Fi allow if policy says so."),
    )
    signup_bonus_granted = models.BooleanField(
        default=False,
        help_text=_("Post-verify one-time bonus already given."),
    )
    premium_trial_activated = models.BooleanField(default=False)
    premium_trial_end_date = models.DateTimeField(null=True, blank=True)

    # Legacy — do not use for new grants
    one_time_quota_granted = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []
    objects = CustomUserManager()

    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ["email"]

    def __str__(self) -> str:
        return self.get_full_name() or self.email

    def save(self, *args, **kwargs) -> None:
        if self.email:
            self.email = self.email.lower().strip()
            if not self.username:
                self.username = self.email
        super().save(*args, **kwargs)

    @property
    def is_university_member(self) -> bool:
        return self.user_type in ("student", "staff")


class GuestAdWatch(models.Model):
    """MAC-level ad watch log (rate limit for pure guest path)."""

    mac_address = models.CharField(max_length=17, db_index=True)
    watched_at = models.DateTimeField(auto_now_add=True)
    reward_granted = models.BooleanField(default=True)

    class Meta:
        ordering = ["-watched_at"]
        verbose_name = "Guest Ad Watch"
        verbose_name_plural = "Guest Ad Watches"

    def __str__(self) -> str:
        return f"{self.mac_address} at {self.watched_at}"
