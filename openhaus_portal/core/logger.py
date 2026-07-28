"""
OpenHaus logging utilities.

Provides structured, consistent logging for all major events.
Services should call these helpers instead of raw logger.* calls.
"""

from __future__ import annotations

import logging
from typing import Any

from accounts.models import CustomUser
from devices.models import Device
from memberships.models import UserMembership
from openhaus_portal.core.constants import LogEvent

logger = logging.getLogger("openhaus")


def log_event(
    event: str,
    message: str,
    *,
    level: int = logging.INFO,
    exc_info: bool = False,
    **context: Any,
) -> None:
    """Log a structured application event with context."""
    details = ""
    if context:
        details = " | ".join(f"{k}={v}" for k, v in context.items())

    logger.log(
        level,
        "[%s] %s%s",
        event,
        message,
        f" | {details}" if details else "",
        exc_info=exc_info,
    )


# ---------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------


def log_login(user: CustomUser, ip_address: str) -> None:
    log_event(
        LogEvent.AUTH_LOGIN,
        "User authenticated successfully.",
        user=user.email,
        ip=ip_address,
    )


def log_logout(user: CustomUser) -> None:
    log_event(
        LogEvent.AUTH_LOGOUT,
        "User logged out.",
        user=user.email,
    )


def log_authentication_failure(email: str, reason: str) -> None:
    log_event(
        LogEvent.AUTH_FAILED,
        "Authentication failed.",
        level=logging.WARNING,
        email=email,
        reason=reason,
    )


# ---------------------------------------------------------------------
# Devices
# ---------------------------------------------------------------------


def log_device_registered(device: Device) -> None:
    log_event(
        LogEvent.DEVICE_REGISTERED,
        "Device registered.",
        user=getattr(device.user, "email", "unknown"),
        mac=device.mac_address,
    )


def log_device_blocked(device: Device) -> None:
    log_event(
        LogEvent.DEVICE_BLOCKED,
        "Device blocked.",
        level=logging.WARNING,
        user=getattr(device.user, "email", "unknown"),
        mac=device.mac_address,
    )


def log_device_unblocked(device: Device) -> None:
    log_event(
        LogEvent.DEVICE_UNBLOCKED,
        "Device unblocked.",
        user=getattr(device.user, "email", "unknown"),
        mac=device.mac_address,
    )


# ---------------------------------------------------------------------
# Memberships
# ---------------------------------------------------------------------


def log_membership_created(membership: UserMembership) -> None:
    log_event(
        LogEvent.MEMBERSHIP_CREATED,
        "Membership created.",
        user=membership.user.email,
        plan=membership.plan.name,
    )


def log_membership_activated(membership: UserMembership) -> None:
    log_event(
        LogEvent.MEMBERSHIP_ACTIVATED,
        "Membership activated.",
        user=membership.user.email,
        plan=membership.plan.name,
    )


def log_membership_renewed(membership: UserMembership) -> None:
    log_event(
        LogEvent.MEMBERSHIP_RENEWED,
        "Membership renewed.",
        user=membership.user.email,
        plan=membership.plan.name,
    )


def log_membership_expired(membership: UserMembership) -> None:
    log_event(
        LogEvent.MEMBERSHIP_EXPIRED,
        "Membership expired.",
        user=membership.user.email,
        plan=membership.plan.name,
    )


def log_membership_cancelled(membership: UserMembership) -> None:
    log_event(
        LogEvent.MEMBERSHIP_CANCELLED,
        "Membership cancelled.",
        user=membership.user.email,
        plan=membership.plan.name,
    )


def log_membership_suspended(membership: UserMembership) -> None:
    log_event(
        LogEvent.MEMBERSHIP_SUSPENDED,
        "Membership suspended.",
        level=logging.WARNING,
        user=membership.user.email,
        plan=membership.plan.name,
    )


# ---------------------------------------------------------------------
# Quota
# ---------------------------------------------------------------------


def log_quota_granted(user: CustomUser, amount_mb: int) -> None:
    log_event(
        LogEvent.QUOTA_GRANTED,
        "Quota granted.",
        user=user.email,
        amount_mb=amount_mb,
    )


def log_quota_consumed(user: CustomUser, amount_mb: int) -> None:
    log_event(
        LogEvent.QUOTA_CONSUMED,
        "Quota consumed.",
        user=user.email,
        amount_mb=amount_mb,
    )


# ---------------------------------------------------------------------
# Sessions & FAS
# ---------------------------------------------------------------------


def log_session_started(user: CustomUser, device: Device) -> None:
    log_event(
        LogEvent.SESSION_STARTED,
        "Network session started.",
        user=user.email,
        mac=device.mac_address,
    )


def log_session_ended(user: CustomUser, device: Device) -> None:
    log_event(
        LogEvent.SESSION_ENDED,
        "Network session ended.",
        user=user.email,
        mac=device.mac_address,
    )


def log_fas_allow(user: CustomUser, device: Device) -> None:
    log_event(
        LogEvent.FAS_ALLOW,
        "Network access granted via FAS.",
        user=user.email,
        mac=device.mac_address,
    )


def log_fas_deny(reason: str, mac_address: str) -> None:
    log_event(
        LogEvent.FAS_DENY,
        "Network access denied.",
        level=logging.WARNING,
        mac=mac_address,
        reason=reason,
    )


# ---------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------


def log_exception(event: str, message: str, **context: Any) -> None:
    log_event(
        event,
        message,
        level=logging.ERROR,
        exc_info=True,
        **context,
    )