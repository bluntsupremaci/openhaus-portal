"""
Authorization Service for OpenHaus.

Orchestrates all checks to determine if a user + device can access the network.
This is the single entry point for network authorization decisions.
"""

from __future__ import annotations

from accounts.models import CustomUser
from devices.models import Device

from openhaus_portal.core.exceptions import (
    AccountInactiveError,
    EmailNotVerifiedError,
    OpenHausError,
)
from openhaus_portal.core import logger
from openhaus_portal.core.constants import LogEvent

from devices.services.devices import DeviceService
from memberships.services.memberships import MembershipService
from quotas.services.quotas import QuotaService
from portal_sessions.services.sessions import SessionService


class AuthorizationService:
    """Central service for network authorization decisions."""

    @staticmethod
    def authorize_network_access(
        *,
        mac_address: str,
        ip_address: str | None = None,
        nas_ip: str | None = None,
    ) -> dict:
        """
        Full authorization pipeline for openNDS FAS.

        Returns openNDS-compatible response dictionary.
        Raises business exceptions on failure.
        """
        try:
            # 1. Device lookup & validation
            device = DeviceService.get_device(mac_address)
            DeviceService.update_last_seen(device)
            user = device.user

            # 2. Full authorization checks
            AuthorizationService._check_account_health(user)
            DeviceService.ensure_device_allowed(device)
            MembershipService.ensure_active_membership(user)
            QuotaService.ensure_available_quota(user, required_bytes=1)

            # 3. Start session
            session = SessionService.start_session(
                user=user,
                device=device,
                ip_address=ip_address,
                nas_ip=nas_ip,
            )

            # 4. Success
            membership = MembershipService.get_active_membership(user)
            quota_remaining = QuotaService.get_available_quota(user)

            logger.log_fas_allow(user=user, device=device)

            return {
                "status": "success",
                "action": "allow",
                "username": user.email,
                "user_type": user.user_type,
                "membership": membership.plan.name,
                "quota_remaining": quota_remaining,
                "session_id": str(session.id),
            }

        except OpenHausError as e:
            logger.log_fas_deny(reason=str(e), mac_address=mac_address)
            raise

    @staticmethod
    def _check_account_health(user: CustomUser) -> None:
        """Basic account validation."""
        if not user.is_active:
            raise AccountInactiveError("Account is disabled.")
        if not user.is_email_verified:
            raise EmailNotVerifiedError("Email verification required.")

    # ============================================================================
    # Helper Methods
    # ============================================================================

    @staticmethod
    def can_login(user: CustomUser) -> bool:
        """Check if user can log into the web portal."""
        try:
            AuthorizationService._check_account_health(user)
            return True
        except OpenHausError:
            return False