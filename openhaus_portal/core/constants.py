"""
Event type constants for structured logging and auditing in OpenHaus.

Use these constants to ensure consistent event naming across the application.
"""

from __future__ import annotations


class LogEvent:
    """Standardized event types for logging and audit trails."""

    # Authentication
    AUTH_LOGIN = "AUTH_LOGIN"
    AUTH_LOGOUT = "AUTH_LOGOUT"
    AUTH_FAILED = "AUTH_FAILED"

    # Device Management
    DEVICE_REGISTERED = "DEVICE_REGISTERED"
    DEVICE_BLOCKED = "DEVICE_BLOCKED"
    DEVICE_UNBLOCKED = "DEVICE_UNBLOCKED"

    # Membership Lifecycle
    MEMBERSHIP_CREATED = "MEMBERSHIP_CREATED"
    MEMBERSHIP_ACTIVATED = "MEMBERSHIP_ACTIVATED"
    MEMBERSHIP_RENEWED = "MEMBERSHIP_RENEWED"
    MEMBERSHIP_EXPIRED = "MEMBERSHIP_EXPIRED"
    MEMBERSHIP_CANCELLED = "MEMBERSHIP_CANCELLED"
    MEMBERSHIP_SUSPENDED = "MEMBERSHIP_SUSPENDED"

    # Session
    SESSION_STARTED = "SESSION_STARTED"
    SESSION_ENDED = "SESSION_ENDED"

    # Quota
    QUOTA_GRANTED = "QUOTA_GRANTED"
    QUOTA_CONSUMED = "QUOTA_CONSUMED"
    QUOTA_EXPIRED = "QUOTA_EXPIRED"
    QUOTA_REFUNDED = "QUOTA_REFUNDED"

    # Captive Portal / FAS
    FAS_ALLOW = "FAS_ALLOW"
    FAS_DENY = "FAS_DENY"

    # General
    SYSTEM_ERROR = "SYSTEM_ERROR"
    ADMIN_ACTION = "ADMIN_ACTION"


# Convenience sets for filtering
AUTH_EVENTS = {
    LogEvent.AUTH_LOGIN,
    LogEvent.AUTH_LOGOUT,
    LogEvent.AUTH_FAILED,
}

MEMBERSHIP_EVENTS = {
    LogEvent.MEMBERSHIP_CREATED,
    LogEvent.MEMBERSHIP_ACTIVATED,
    LogEvent.MEMBERSHIP_RENEWED,
    LogEvent.MEMBERSHIP_EXPIRED,
    LogEvent.MEMBERSHIP_CANCELLED,
    LogEvent.MEMBERSHIP_SUSPENDED,
}