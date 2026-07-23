"""
OpenHaus Quota Service.

Centralized business logic for quota allocation, consumption,
validation, expiration, and reporting.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from django.db import models, transaction
from django.db.models import QuerySet, Sum
from django.utils import timezone

from accounts.models import CustomUser
from quotas.models import QuotaAllocation, QuotaType, QuotaUsage

from openhaus_portal.core import logger
from openhaus_portal.core.exceptions import (
    InsufficientQuotaError,
    QuotaExpiredError,
    QuotaNotFoundError,
)


class QuotaService:
    """Service class for all quota-related business logic."""

    # ============================================================================
    # Query Methods
    # ============================================================================

    @staticmethod
    def get_active_allocations(user: CustomUser) -> QuerySet[QuotaAllocation]:
        """Return active, non-expired allocations (priority: soonest expiry)."""
        return QuotaAllocation.objects.select_related("user").filter(
            user=user,
            is_active=True,
            expires_at__gt=timezone.now(),
            used_bytes__lt=models.F("total_bytes"),
        ).order_by("expires_at", "granted_at", "created_at")

    @staticmethod
    def get_available_quota(user: CustomUser) -> int:
        """Total remaining bytes across all active allocations."""
        result = QuotaService.get_active_allocations(user).aggregate(
            total=Sum(models.F("total_bytes") - models.F("used_bytes"))
        )
        return result["total"] or 0

    @staticmethod
    def has_available_quota(user: CustomUser) -> bool:
        """Quick check for any usable quota."""
        return QuotaService.get_available_quota(user) > 0

    @staticmethod
    def get_primary_allocation(user: CustomUser) -> QuotaAllocation:
        """Allocation that will be consumed first (earliest expiry)."""
        allocation = QuotaService.get_active_allocations(user).first()
        if allocation is None:
            raise QuotaNotFoundError("No active quota allocation exists.")
        return allocation

    # ============================================================================
    # Consumption (Critical Feature)
    # ============================================================================

    @staticmethod
    def consume_quota(
        user: CustomUser,
        bytes_to_consume: int,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Consume quota from the soonest-expiring allocation(s).

        Creates immutable QuotaUsage records.
        """
        if bytes_to_consume <= 0:
            return

        with transaction.atomic():
            remaining = bytes_to_consume
            allocations = list(QuotaService.get_active_allocations(user))

            for allocation in allocations:
                if remaining <= 0:
                    break

                available = allocation.remaining_bytes
                to_consume = min(available, remaining)

                allocation.used_bytes += to_consume
                allocation.save(update_fields=["used_bytes", "updated_at"])

                QuotaUsage.objects.create(
                    allocation=allocation,
                    bytes_used=to_consume,
                    metadata=metadata or {},
                )

                remaining -= to_consume

            if remaining > 0:
                raise InsufficientQuotaError(
                    f"Could not consume {bytes_to_consume:,} bytes — insufficient quota."
                )

            logger.log_quota_consumed(
                user=user,
                amount_mb=bytes_to_consume // (1024 * 1024),
            )

    # ============================================================================
    # Dashboard / Status Methods
    # ============================================================================

    @staticmethod
    def get_quota_status(user: CustomUser) -> dict[str, Any]:
        """Comprehensive quota status for dashboards and templates."""
        try:
            summary = QuotaService.get_quota_summary(user)
            primary = QuotaService.get_primary_allocation(user)

            return {
                "available_bytes": summary["available_bytes"],
                "available_gb": round(summary["available_bytes"] / (1024**3), 2),
                "allocation_count": summary["allocation_count"],
                "primary_allocation": {
                    "id": primary.id,
                    "type": primary.quota_type,
                    "type_display": primary.get_quota_type_display(),
                    "remaining_bytes": primary.remaining_bytes,
                    "remaining_gb": round(primary.remaining_bytes / (1024**3), 2),
                    "expires_at": primary.expires_at,
                },
                "is_sufficient": QuotaService.has_available_quota(user),
                "total_consumed_bytes": QuotaService.get_total_consumed(user),
            }
        except (QuotaNotFoundError, QuotaExpiredError):
            return {
                "available_bytes": 0,
                "available_gb": 0.0,
                "allocation_count": 0,
                "primary_allocation": None,
                "is_sufficient": False,
                "total_consumed_bytes": 0,
            }

    @staticmethod
    def get_quota_summary(user: CustomUser) -> dict[str, Any]:
        """Complete quota summary for API, dashboard, captive portal."""
        allocations = list(QuotaService.get_active_allocations(user))

        return {
            "available_bytes": QuotaService.get_available_quota(user),
            "allocation_count": len(allocations),
            "allocations": [
                {
                    "id": a.id,
                    "type": a.quota_type,
                    "type_display": a.get_quota_type_display(),
                    "total_bytes": a.total_bytes,
                    "remaining_bytes": a.remaining_bytes,
                    "consumed_bytes": a.consumed_bytes,
                    "expires_at": a.expires_at,
                }
                for a in allocations
            ],
        }

    # ============================================================================
    # Validation
    # ============================================================================

    @staticmethod
    def ensure_available_quota(user: CustomUser, required_bytes: int = 1) -> None:
        """Enforce sufficient quota before network access or usage."""
        if required_bytes <= 0:
            raise ValueError("required_bytes must be greater than zero.")

        if not QuotaService.get_active_allocations(user).exists():
            if QuotaAllocation.objects.filter(user=user, is_active=True).exists():
                raise QuotaExpiredError("All quota allocations have expired.")
            raise QuotaNotFoundError("No quota allocation exists.")

        if QuotaService.get_available_quota(user) < required_bytes:
            raise InsufficientQuotaError(
                f"Requested {required_bytes:,} bytes but only "
                f"{QuotaService.get_available_quota(user):,} bytes remain."
            )

    # ============================================================================
    # Reporting & History
    # ============================================================================

    @staticmethod
    def get_usage_history(user: CustomUser) -> QuerySet[QuotaUsage]:
        """Usage history for user dashboard / admin reports."""
        return QuotaUsage.objects.select_related("allocation__user").filter(
            allocation__user=user
        ).order_by("-recorded_at")

    @staticmethod
    def get_total_consumed(user: CustomUser) -> int:
        """Total bytes ever consumed by user."""
        result = QuotaService.get_usage_history(user).aggregate(
            total=Sum("bytes_used")
        )
        return result["total"] or 0

    # ============================================================================
    # Allocation Creation (Internal Factory)
    # ============================================================================

    @staticmethod
    def _create_allocation(
        *,
        user: CustomUser,
        quota_type: QuotaType,
        total_bytes: int,
        expires_at: datetime,
        notes: str = "",
    ) -> QuotaAllocation:
        """Internal factory for all quota grants."""
        if total_bytes <= 0:
            raise ValueError("total_bytes must be greater than zero.")
        if expires_at <= timezone.now():
            raise ValueError("expires_at must be in the future.")

        with transaction.atomic():
            allocation = QuotaAllocation.objects.create(
                user=user,
                quota_type=quota_type,
                total_bytes=total_bytes,
                used_bytes=0,
                granted_at=timezone.now(),
                expires_at=expires_at,
                notes=notes,
            )

            logger.log_quota_granted(user=user, amount_mb=total_bytes // (1024 * 1024))
            return allocation

    @staticmethod
    def grant_daily_free_quota(
        *, user: CustomUser, total_bytes: int, expires_at: datetime
    ) -> QuotaAllocation:
        """Grant daily free allowance or guest reward."""
        if total_bytes <= 0:
            raise ValueError("total_bytes must be greater than zero.")

        return QuotaService._create_allocation(
            user=user,
            quota_type=QuotaType.FREE_DAILY,
            total_bytes=total_bytes,
            expires_at=expires_at,
            notes="Guest ad reward / daily free quota",
        )

    @staticmethod
    def grant_membership_quota(
        *, user: CustomUser, total_bytes: int, expires_at: datetime
    ) -> QuotaAllocation:
        """Grant quota from membership plan."""
        return QuotaService._create_allocation(
            user=user,
            quota_type=QuotaType.MEMBERSHIP,
            total_bytes=total_bytes,
            expires_at=expires_at,
            notes="Membership allocation",
        )
    
    @staticmethod
    def grant_welcome_gift(user: CustomUser, total_bytes: int = 5 * 1024 * 1024 * 1024):
        """Grant one-time welcome data gift to non-students."""
        if user.one_time_quota_granted:
            return

        QuotaService.grant_daily_free_quota(
            user=user,
            total_bytes=total_bytes,
            expires_at=timezone.now() + timezone.timedelta(days=30)
        )

        user.one_time_quota_granted = True
        user.save(update_fields=['one_time_quota_granted'])

        logger.log_event("WELCOME_GIFT_GRANTED", "Welcome 500MB gift granted", user=user, extra={"gb": total_bytes / (1024**3)})