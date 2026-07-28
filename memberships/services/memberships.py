"""
OpenHaus Membership Service.

Centralized business logic for membership lifecycle:
creation, activation, renewal, expiration, validation, and reporting.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db import models, transaction
from django.db.models import Count, QuerySet
from django.utils import timezone

from accounts.models import CustomUser
from memberships.models import (
    MembershipPlan,
    MembershipStatus,
    UserMembership,
)
from openhaus_portal.core import logger
from openhaus_portal.core.exceptions import (
    ActiveMembershipExistsError,
    MembershipExpiredError,
    MembershipNotFoundError,
)

# Import inside methods where needed to avoid circular imports
# from quotas.services.quotas import QuotaService


class MembershipService:
    """Service class for all membership-related business logic."""

    # ============================================================================
    # Query Methods
    # ============================================================================

    @staticmethod
    def get_user_memberships(user: CustomUser) -> QuerySet[UserMembership]:
        """Return all memberships for a user (historical included)."""
        return (
            UserMembership.objects.select_related("user", "plan")
            .filter(user=user)
            .order_by("-created_at")
        )

    @staticmethod
    def get_active_membership(user: CustomUser) -> UserMembership:
        """Return the user's active membership or raise error."""
        membership = (
            UserMembership.objects.select_related("plan")
            .filter(
                user=user,
                status=MembershipStatus.ACTIVE,
                end_date__gt=timezone.now(),
            )
            .first()
        )

        if membership is None:
            raise MembershipNotFoundError("No active membership exists.")

        return membership

    @staticmethod
    def has_active_membership(user: CustomUser) -> bool:
        """Check if user has an active membership."""
        return UserMembership.objects.filter(
            user=user,
            status=MembershipStatus.ACTIVE,
            end_date__gt=timezone.now(),
        ).exists()

    @staticmethod
    def get_membership_status(user: CustomUser) -> dict[str, Any]:
        """Status summary for APIs, dashboards, and captive portal."""
        try:
            membership = MembershipService.get_active_membership(user)
            return {
                "has_membership": True,
                "status": membership.status,
                "plan": membership.plan.name,
                "expires_at": membership.end_date,
                "remaining_days": membership.remaining_days,
                "remaining_seconds": membership.remaining_seconds,
            }
        except MembershipNotFoundError:
            return {
                "has_membership": False,
                "status": None,
                "plan": None,
                "expires_at": None,
                "remaining_days": 0,
                "remaining_seconds": 0,
            }

    # ============================================================================
    # Creation & Activation
    # ============================================================================

    @staticmethod
    def create_membership(
        *,
        user: CustomUser,
        plan: MembershipPlan,
        start_date: timezone.datetime | None = None,
    ) -> UserMembership:
        """Create a new PENDING membership."""
        if not plan.is_active:
            raise ValueError("Cannot create membership from an inactive plan.")

        if MembershipService.has_active_membership(user):
            raise ActiveMembershipExistsError("User already has an active membership.")

        if start_date is None:
            start_date = timezone.now()

        end_date = start_date + timedelta(days=plan.duration_days)

        with transaction.atomic():
            membership = UserMembership.objects.create(
                user=user,
                plan=plan,
                status=MembershipStatus.PENDING,
                start_date=start_date,
                end_date=end_date,
            )

        logger.log_membership_created(membership=membership)
        return membership

    @staticmethod
    def activate_membership(membership: UserMembership) -> UserMembership:
        """Activate a pending membership."""
        with transaction.atomic():
            membership = (
                UserMembership.objects.select_for_update()
                .select_related("plan", "user")
                .get(pk=membership.pk)
            )

            if membership.status != MembershipStatus.PENDING:
                raise ValueError("Only pending memberships can be activated.")

            if MembershipService.has_active_membership(membership.user):
                raise ActiveMembershipExistsError("User already has an active membership.")

            now = timezone.now()
            membership.start_date = now
            membership.end_date = now + timedelta(days=membership.plan.duration_days)
            membership.status = MembershipStatus.ACTIVE

            membership.save(
                update_fields=["status", "start_date", "end_date", "updated_at"]
            )

            MembershipService._assign_membership_quota(membership)
            logger.log_membership_activated(membership=membership)

            return membership

    # ============================================================================
    # Internal Helpers
    # ============================================================================

    @staticmethod
    def _assign_membership_quota(membership: UserMembership):
        """Internal method to grant quota when membership becomes active."""
        from quotas.services.quotas import QuotaService

        plan = membership.plan
        if plan.included_quota_gb <= 0:
            return None

        total_bytes = plan.included_quota_gb * (1024**3)

        return QuotaService.grant_membership_quota(
            user=membership.user,
            total_bytes=total_bytes,
            expires_at=membership.end_date,
        )

    # ============================================================================
    # Lifecycle Management
    # ============================================================================

    @staticmethod
    def renew_membership(membership: UserMembership) -> UserMembership:
        """Renew/extend an existing membership."""
        with transaction.atomic():
            membership = (
                UserMembership.objects.select_for_update()
                .select_related("plan", "user")
                .get(pk=membership.pk)
            )

            if membership.status in (MembershipStatus.CANCELLED, MembershipStatus.SUSPENDED):
                raise ValueError("This membership cannot be renewed.")

            now = timezone.now()
            start_date = now if membership.end_date and membership.end_date < now else membership.end_date or now

            membership.end_date = start_date + timedelta(days=membership.plan.duration_days)
            membership.start_date = start_date
            membership.status = MembershipStatus.ACTIVE

            membership.save(
                update_fields=["status", "start_date", "end_date", "updated_at"]
            )

            MembershipService._assign_membership_quota(membership)
            logger.log_membership_renewed(membership=membership)

            return membership

    @staticmethod
    def expire_memberships() -> int:
        """Batch expire active memberships (scheduled task)."""
        now = timezone.now()
        expired_count = 0

        memberships = UserMembership.objects.filter(
            status=MembershipStatus.ACTIVE,
            end_date__lte=now,
        )

        with transaction.atomic():
            for membership in memberships.select_for_update():
                membership.status = MembershipStatus.EXPIRED
                membership.save(update_fields=["status", "updated_at"])
                logger.log_membership_expired(membership=membership)
                expired_count += 1

        return expired_count

    @staticmethod
    def cancel_membership(membership: UserMembership) -> UserMembership:
        """Cancel membership."""
        with transaction.atomic():
            membership = UserMembership.objects.select_for_update().get(pk=membership.pk)
            membership.status = MembershipStatus.CANCELLED
            membership.save(update_fields=["status", "updated_at"])

            logger.log_membership_cancelled(membership=membership)
            return membership

    @staticmethod
    def suspend_membership(membership: UserMembership) -> UserMembership:
        """Suspend membership."""
        with transaction.atomic():
            membership = UserMembership.objects.select_for_update().get(pk=membership.pk)
            membership.status = MembershipStatus.SUSPENDED
            membership.save(update_fields=["status", "updated_at"])

            logger.log_membership_suspended(membership=membership)
            return membership

    # ============================================================================
    # Validation & Access Control
    # ============================================================================

    @staticmethod
    def ensure_active_membership(user: CustomUser) -> UserMembership:
        """Strict check used by FAS and protected endpoints."""
        try:
            membership = MembershipService.get_active_membership(user)
        except MembershipNotFoundError:
            if UserMembership.objects.filter(
                user=user, status=MembershipStatus.EXPIRED
            ).exists():
                raise MembershipExpiredError("Membership has expired.")
            raise

        if membership.has_expired:
            raise MembershipExpiredError("Membership has expired.")

        return membership

    @staticmethod
    def can_access_membership_features(user: CustomUser) -> bool:
        """Check if user can access membership-only features."""
        try:
            MembershipService.ensure_active_membership(user)
            return True
        except (MembershipNotFoundError, MembershipExpiredError):
            return False

    @staticmethod
    def get_membership_device_limit(user: CustomUser) -> int:
        """Return max devices allowed by current plan."""
        membership = MembershipService.ensure_active_membership(user)
        return membership.plan.max_devices

    @staticmethod
    def get_membership_speed_limit(user: CustomUser) -> int:
        """Return speed limit in Mbps (0 = unlimited)."""
        membership = MembershipService.ensure_active_membership(user)
        return membership.plan.speed_limit_mbps

    # ============================================================================
    # Reporting & Analytics
    # ============================================================================

    @staticmethod
    def get_membership_summary(user: CustomUser) -> dict[str, Any]:
        """Complete membership summary for dashboards and APIs."""
        try:
            membership = MembershipService.get_active_membership(user)
            return {
                "has_membership": True,
                "membership_id": membership.id,
                "status": membership.status,
                "plan": {
                    "id": membership.plan.id,
                    "name": membership.plan.name,
                    "duration_days": membership.plan.duration_days,
                    "quota_gb": membership.plan.included_quota_gb,
                    "max_devices": membership.plan.max_devices,
                    "speed_limit_mbps": membership.plan.speed_limit_mbps,
                },
                "start_date": membership.start_date,
                "end_date": membership.end_date,
                "remaining_days": membership.remaining_days,
                "remaining_seconds": membership.remaining_seconds,
            }
        except MembershipNotFoundError:
            return {
                "has_membership": False,
                "membership_id": None,
                "status": None,
                "plan": None,
                "start_date": None,
                "end_date": None,
                "remaining_days": 0,
                "remaining_seconds": 0,
            }

    @staticmethod
    def get_expiring_memberships(days: int = 7) -> QuerySet[UserMembership]:
        """Memberships expiring soon."""
        expiry_date = timezone.now() + timedelta(days=days)
        return (
            UserMembership.objects.select_related("user", "plan")
            .filter(
                status=MembershipStatus.ACTIVE,
                end_date__lte=expiry_date,
                end_date__gt=timezone.now(),
            )
            .order_by("end_date")
        )

    @staticmethod
    def get_membership_statistics() -> dict[str, int]:
        """Global statistics for admin dashboards."""
        result = UserMembership.objects.aggregate(
            total=Count("id"),
            active=Count("id", filter=models.Q(status=MembershipStatus.ACTIVE)),
            expired=Count("id", filter=models.Q(status=MembershipStatus.EXPIRED)),
            cancelled=Count("id", filter=models.Q(status=MembershipStatus.CANCELLED)),
        )

        return {
            "total_memberships": result["total"] or 0,
            "active_memberships": result["active"] or 0,
            "expired_memberships": result["expired"] or 0,
            "cancelled_memberships": result["cancelled"] or 0,
        }

    @staticmethod
    def get_available_plans() -> QuerySet[MembershipPlan]:
        """Active plans available for selection."""
        return MembershipPlan.objects.filter(is_active=True).order_by(
            "duration_days", "price"
        )
    
    @staticmethod
    def grant_premium_trial(user, months: int = 1):
        """Grant 1-month premium trial to new verified students."""
        from datetime import timedelta

        # Create a new membership using existing method
        try:
            plan = MembershipPlan.objects.get(name__icontains="Premium")
        except MembershipPlan.DoesNotExist:
            # Fallback - create a basic premium plan if none exists
            plan = MembershipPlan.objects.create(
                name="Premium Trial",
                duration_days=30 * months,
                included_quota_gb=0,
                price=0,
                is_active=True,
                max_devices=5,
            )

        membership = MembershipService.create_membership(
            user=user,
            plan=plan,
            start_date=timezone.now()
        )

        MembershipService.activate_membership(membership)  

        logger.log_event("PREMIUM_TRIAL_GRANTED", user=user, extra={"months": months})