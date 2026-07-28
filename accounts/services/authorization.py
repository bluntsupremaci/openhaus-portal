"""
Authorization Service for OpenHaus.

Single entry point for network authorization decisions (FAS and internal use).
"""

from __future__ import annotations

from accounts.models import CustomUser
from devices.models import Device
from devices.services.devices import DeviceService
from memberships.services.memberships import MembershipService
from openhaus_portal.core import logger
from openhaus_portal.core.exceptions import (
    AccountInactiveError,
    EmailNotVerifiedError,
    InsufficientQuotaError,
    MembershipExpiredError,
    MembershipNotFoundError,
    OpenHausError,
    QuotaExpiredError,
    QuotaNotFoundError,
)
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
        require_membership: bool = True,
    ) -> dict:
        """
        Full authorization pipeline for openNDS FAS.

        Returns a result dict. Does not perform HTTP redirects.
        Raises OpenHausError subclasses on failure.
        """
        mac = DeviceService.normalize_mac(mac_address)

        try:
            device = DeviceService.get_device(mac)
            DeviceService.update_last_seen(device)
            user = device.user

            AuthorizationService._check_account_health(user)
            DeviceService.ensure_device_allowed(device)

            membership = None
            if require_membership:
                try:
                    membership = MembershipService.ensure_active_membership(user)
                except (MembershipNotFoundError, MembershipExpiredError):
                    # Guests may proceed on quota-only access.
                    if user.user_type != "guest":
                        raise
                    if not QuotaService.has_available_quota(user):
                        raise

            QuotaService.ensure_available_quota(user, required_bytes=1)

            session = SessionService.start_session(
                user=user,
                device=device,
                ip_address=ip_address,
                nas_ip=nas_ip,
            )

            if membership is None:
                try:
                    membership = MembershipService.get_active_membership(user)
                except MembershipNotFoundError:
                    membership = None

            quota_remaining = QuotaService.get_available_quota(user)
            logger.log_fas_allow(user=user, device=device)

            return {
                "status": "success",
                "action": "allow",
                "username": user.email,
                "user_type": user.user_type,
                "membership": membership.plan.name if membership else "None",
                "quota_remaining": quota_remaining,
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
        """
        Validate that user+device may access the network.
        Raises OpenHausError on denial. Does not start a session.
        """
        AuthorizationService._check_account_health(user)
        DeviceService.ensure_device_allowed(device)
        try:
            MembershipService.ensure_active_membership(user)
        except (MembershipNotFoundError, MembershipExpiredError):
            if user.user_type != "guest":
                raise
            if not QuotaService.has_available_quota(user):
                raise
        QuotaService.ensure_available_quota(user, required_bytes=1)

    @staticmethod
    def _check_account_health(user: CustomUser) -> None:
        if not user.is_active:
            raise AccountInactiveError("Account is disabled.")
        # Guests created for captive portal are marked verified.
        if not user.is_email_verified and user.user_type != "guest":
            raise EmailNotVerifiedError("Email verification required.")

    @staticmethod
    def can_login(user: CustomUser) -> bool:
        try:
            AuthorizationService._check_account_health(user)
            return True
        except OpenHausError:
            return False