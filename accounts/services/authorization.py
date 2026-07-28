"""
Authorization Service for OpenHaus.

Single entry point for network authorization (FAS and internal use).
Order: device → account → membership OR time grant → session.
"""

from __future__ import annotations

from access_policy.services import AccessPolicyService
from accounts.models import CustomUser
from devices.models import Device
from devices.services.devices import DeviceService
from memberships.services.memberships import MembershipService
from openhaus_portal.core import logger
from openhaus_portal.core.exceptions import AccountInactiveError, OpenHausError
from portal_sessions.services.sessions import SessionService
from quotas.services.quotas import QuotaService


class AuthorizationService:
    """Central service for network authorization decisions."""

    @staticmethod
    def authorize_network_access(
        *,
        mac_address: str,
        ip_address: str | None = None,
        nas_ip: str | None = None,
        hostname: str | None = None,
        platform: str | None = None,
        **_,
    ) -> dict:
        """
        Full authorization pipeline for openNDS FAS.

        Returns a result dict (no HTTP). Raises OpenHausError on denial.
        """
        mac = DeviceService.normalize_mac(mac_address)

        try:
            device = DeviceService.get_device(mac)
            DeviceService.update_last_seen(device)
            DeviceService.ensure_device_allowed(device)
            user = device.user

            if not user.is_active:
                raise AccountInactiveError("Account is disabled.")

            # Membership OR signup/verify/daily/ad time grant
            AccessPolicyService.ensure_access_for_authorization(user)

            session = SessionService.start_session(
                user=user,
                device=device,
                ip_address=ip_address,
                nas_ip=nas_ip,
            )

            membership = None
            try:
                membership = MembershipService.get_active_membership(user)
            except Exception:
                membership = None

            try:
                quota_remaining = QuotaService.get_available_quota(user)
            except Exception:
                quota_remaining = 0

            logger.log_fas_allow(user=user, device=device)

            return {
                "status": "success",
                "action": "allow",
                "username": user.email,
                "user_type": user.user_type,
                "role": AccessPolicyService.resolve_role(user),
                "membership": membership.plan.name if membership else "None",
                "quota_remaining": quota_remaining,
                "grant_seconds_remaining": AccessPolicyService.total_remaining_seconds(
                    user
                ),
                "session_id": str(session.id),
                "user": user,
                "device": device,
                "session": session,
            }

        except OpenHausError as e:
            logger.log_fas_deny(reason=str(e), mac_address=mac)
            raise

    @staticmethod
    def can_access_network(*, user: CustomUser, device: Device) -> None:
        """Validate access without starting a session."""
        if not user.is_active:
            raise AccountInactiveError("Account is disabled.")
        DeviceService.ensure_device_allowed(device)
        AccessPolicyService.ensure_access_for_authorization(user)

    @staticmethod
    def can_login(user: CustomUser) -> bool:
        return bool(user.is_active and user.is_email_verified)

