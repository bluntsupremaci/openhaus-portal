"""
OpenHaus Membership Models.

Defines subscription plans and user-specific memberships.

All business rules (renewal, expiration, validation, etc.)
are handled in the service layer.
"""

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from accounts.models import CustomUser


class MembershipStatus(models.TextChoices):
    """Membership lifecycle states."""

    PENDING = "PENDING", _("Pending")
    ACTIVE = "ACTIVE", _("Active")
    EXPIRED = "EXPIRED", _("Expired")
    SUSPENDED = "SUSPENDED", _("Suspended")
    CANCELLED = "CANCELLED", _("Cancelled")


class MembershipPlan(models.Model):
    """Subscription plan template defining resources and pricing."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    name = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
    )
    slug = models.SlugField(
        unique=True,
        db_index=True,
        help_text=_("Unique identifier for API/frontend use."),
    )
    description = models.TextField(blank=True)

    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    currency = models.CharField(max_length=3, default="NGN")

    duration_days = models.PositiveIntegerField(help_text=_("Duration of the plan in days."))
    included_quota_gb = models.PositiveIntegerField(
        default=0,
        help_text=_("Data quota included (GB)."),
    )
    max_devices = models.PositiveSmallIntegerField(
        default=3,
        help_text=_("Maximum number of registered devices."),
    )
    speed_limit_mbps = models.PositiveIntegerField(
        default=0,
        help_text=_("0 = Unlimited speed."),
    )

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Membership Plan")
        verbose_name_plural = _("Membership Plans")
        ordering = ["duration_days", "price"]

    def __str__(self) -> str:
        return self.name


class UserMembership(models.Model):
    """User-specific membership subscription.

    A user can have many historical records but only one ACTIVE at a time.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    plan = models.ForeignKey(
        MembershipPlan,
        on_delete=models.PROTECT,
        related_name="user_memberships",
    )

    status = models.CharField(
        max_length=20,
        choices=MembershipStatus.choices,
        default=MembershipStatus.PENDING,
        db_index=True,
    )

    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("User Membership")
        verbose_name_plural = _("User Memberships")
        ordering = ["-end_date"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["status", "end_date"]),
        ]

    def clean(self) -> None:
        """Validate date consistency."""
        super().clean()
        if self.end_date and self.end_date <= self.start_date:
            raise ValidationError(_("End date must be after the start date."))

    @property
    def is_valid(self) -> bool:
        """True if currently active and not expired."""
        return self.status == MembershipStatus.ACTIVE and self.end_date > timezone.now()

    @property
    def has_expired(self) -> bool:
        """True if past end_date."""
        return timezone.now() >= self.end_date

    @property
    def remaining_days(self) -> int:
        """Days remaining (0 if expired)."""
        if self.has_expired or not self.end_date:
            return 0
        return (self.end_date - timezone.now()).days

    @property
    def remaining_seconds(self) -> int:
        """Seconds remaining (0 if expired)."""
        if self.has_expired or not self.end_date:
            return 0
        return int((self.end_date - timezone.now()).total_seconds())

    def save(self, *args, **kwargs) -> None:
        """Full validation on save."""
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.user.email} | {self.plan.name} | {self.get_status_display()}"
