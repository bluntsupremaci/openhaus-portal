"""
OpenHaus Quota Models.

Represents quota allocations and immutable usage records.

All business logic (allocation, consumption, validation)
lives in quotas/services/quotas.py.
"""

from __future__ import annotations

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from accounts.models import CustomUser
# from devices.models import Device  # Uncomment when Device model is ready


class QuotaType(models.TextChoices):
    """Types/sources of quota allocations."""

    FREE_DAILY = "FREE_DAILY", _("Daily Free")
    MEMBERSHIP = "MEMBERSHIP", _("Membership")
    GIFT = "GIFT", _("Gift")
    BONUS = "BONUS", _("Bonus")
    MANUAL = "MANUAL", _("Manual")


class QuotaAllocation(models.Model):
    """A granted quota block for a user (or optionally device)."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="quota_allocations",
    )
    # device = models.ForeignKey(...)  # Optional device-specific quota (future)

    quota_type = models.CharField(
        max_length=30,
        choices=QuotaType.choices,
        default=QuotaType.MEMBERSHIP,
    )

    total_bytes = models.BigIntegerField(
        help_text="Total allocated quota in bytes."
    )
    used_bytes = models.BigIntegerField(
        default=0,
        help_text="Bytes already consumed."
    )

    granted_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()

    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Quota Allocation")
        verbose_name_plural = _("Quota Allocations")
        ordering = ["expires_at", "-created_at"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["quota_type"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["user", "expires_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.email} | {self.get_quota_type_display()} | {self.remaining_bytes:,} bytes left"

    @property
    def remaining_bytes(self) -> int:
        """Current remaining quota."""
        return max(0, self.total_bytes - self.used_bytes)

    @property
    def consumed_bytes(self) -> int:
        """Bytes already used."""
        return self.used_bytes

    def clean(self) -> None:
        super().clean()

        if self.total_bytes < 0:
            raise ValidationError("Total quota cannot be negative.")
        if self.used_bytes < 0:
            raise ValidationError("Used bytes cannot be negative.")
        if self.used_bytes > self.total_bytes:
            raise ValidationError("Used bytes cannot exceed total quota.")
        if self.expires_at <= self.granted_at:
            raise ValidationError("Expiration must be after grant time.")

    def save(self, *args, **kwargs) -> None:
        self.full_clean()
        super().save(*args, **kwargs)


class QuotaUsage(models.Model):
    """Immutable audit log of quota consumption.

    One record per deduction event.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    allocation = models.ForeignKey(
        QuotaAllocation,
        on_delete=models.CASCADE,
        related_name="usage_records",
    )

    bytes_used = models.BigIntegerField()
    recorded_at = models.DateTimeField(auto_now_add=True)

    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = _("Quota Usage")
        verbose_name_plural = _("Quota Usage Records")
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(fields=["recorded_at"]),
            models.Index(fields=["allocation"]),
        ]

    def __str__(self) -> str:
        return f"{self.allocation.user.email} | {self.bytes_used:,} bytes used"

    def clean(self) -> None:
        super().clean()
        if self.bytes_used <= 0:
            raise ValidationError("Bytes used must be greater than zero.")

    def save(self, *args, **kwargs) -> None:
        if self.pk:
            raise ValidationError("Quota usage records are immutable.")
        self.full_clean()
        super().save(*args, **kwargs)