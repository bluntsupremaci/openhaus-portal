"""
Custom exceptions for OpenHaus backend.

Services raise these for business rule violations.
Views/APIs translate them into appropriate HTTP responses.
"""


class OpenHausError(Exception):
    """Base exception for all OpenHaus errors."""


# ============================================================================
# Authentication
# ============================================================================


class AuthenticationError(OpenHausError):
    """Base for authentication-related errors."""


class InvalidCredentialsError(AuthenticationError):
    """Invalid email or password provided."""


class EmailNotVerifiedError(AuthenticationError):
    """Email address has not been verified."""


class AccountInactiveError(AuthenticationError):
    """Account is inactive or disabled."""


# ============================================================================
# Authorization
# ============================================================================


class AuthorizationError(OpenHausError):
    """User lacks permission for the requested action."""


# ============================================================================
# Device
# ============================================================================


class DeviceError(OpenHausError):
    """Base for device-related errors."""


class DeviceNotFoundError(DeviceError):
    """Device record not found."""


class DeviceBlockedError(DeviceError):
    """Device has been administratively blocked."""


class DeviceAlreadyRegisteredError(DeviceError):
    """Device is already registered to another user."""


# ============================================================================
# Membership
# ============================================================================


class MembershipError(OpenHausError):
    """Base for membership-related errors."""


class MembershipNotFoundError(MembershipError):
    """User has no valid membership."""


class MembershipExpiredError(MembershipError):
    """Membership has reached its end date."""


class ActiveMembershipExistsError(MembershipError):
    """User already has an active membership (prevents duplicates)."""


# ============================================================================
# Quota
# ============================================================================


class QuotaError(OpenHausError):
    """Base for quota-related errors."""


class QuotaNotFoundError(QuotaError):
    """No active quota allocation found."""


class QuotaExpiredError(QuotaError):
    """All quota allocations have expired."""


class InsufficientQuotaError(QuotaError):
    """Available quota is insufficient for the request."""


# ============================================================================
# Session
# ============================================================================


class SessionError(OpenHausError):
    """Base for session-related errors."""


class SessionNotFoundError(SessionError):
    """WiFi session not found."""


class SessionExpiredError(SessionError):
    """Session has expired."""


class ActiveSessionExistsError(SessionError):
    """An active session already exists for this device/user."""


class SessionLimitExceededError(SessionError):
    """Maximum number of concurrent sessions reached."""