"""Payment records for Paystack-backed membership purchases."""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from memberships.models import MembershipPlan, UserMembership


class PaymentStatus(models.TextChoices):
    PENDING = "pending", _("Pending")
    SUCCESS = "success", _("Success")
    FAILED = "failed", _("Failed")
    ABANDONED = "abandoned", _("Abandoned")


class Payment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    plan = models.ForeignKey(
        MembershipPlan,
        on_delete=models.PROTECT,
        related_name="payments",
    )
    membership = models.ForeignKey(
        UserMembership,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payments",
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text=_("Amount in major currency units (e.g. NGN), not kobo."),
    )
    currency = models.CharField(max_length=3, default="NGN")

    reference = models.CharField(max_length=100, unique=True, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=PaymentStatus.choices,
        default=PaymentStatus.PENDING,
        db_index=True,
    )

    paystack_access_code = models.CharField(max_length=100, blank=True)
    raw_verify_response = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Payment")
        verbose_name_plural = _("Payments")

    def __str__(self) -> str:
        return f"{self.reference} | {self.user} | {self.status}"

    @property
    def amount_kobo(self) -> int:
        """Paystack expects integer kobo for NGN."""
        return int((self.amount * Decimal("100")).quantize(Decimal("1")))
