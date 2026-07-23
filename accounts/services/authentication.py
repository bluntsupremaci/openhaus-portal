"""
Authentication Service for OpenHaus.

Handles user identification, credential validation, and account management.
"""

from __future__ import annotations

from typing import Optional

from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.http import HttpRequest
from django.utils import timezone

from accounts.models import CustomUser
from openhaus_portal.core.exceptions import (
    AccountInactiveError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
)
from quotas.services.quotas import QuotaService
from openhaus_portal.core import logger


class AuthService:
    """Service class for authentication and account management."""

    @staticmethod
    def authenticate_client(*, email: str, password: str) -> CustomUser:
        """Authenticate user by email + password."""
        email = CustomUser.objects.normalize_email(email)

        user = authenticate(username=email, password=password)

        if user is None:
            raise InvalidCredentialsError("Invalid email or password.")

        AuthService.ensure_active_account(user)
        AuthService.ensure_verified_email(user)

        return user

    @staticmethod
    def grant_temporary_access(user: CustomUser):
        """Give limited access immediately after signup."""
        if user.is_email_verified or user.one_time_quota_granted:
            return

        try:
            with transaction.atomic():
                QuotaService.grant_welcome_gift(
                    user=user,
                    total_bytes=500 * 1024 * 1024 
                )

                user.one_time_quota_granted = True
                user.save(update_fields=['one_time_quota_granted'])

                logger.log_event("TEMPORARY_ACCESS_GRANTED", "Temporary 500MB access granted", user=user)
        except Exception as e:
            logger.log_exception("TEMPORARY_ACCESS_ERROR", str(e), user=user)

    @staticmethod
    def get_user_by_email(email: str) -> Optional[CustomUser]:
        """Retrieve user by email (case-insensitive)."""
        email = CustomUser.objects.normalize_email(email)
        return CustomUser.objects.filter(email__iexact=email).first()

    @staticmethod
    def login_user(*, request: HttpRequest, user: CustomUser) -> None:
        """Create Django session for user."""
        login(request, user)

    @staticmethod
    def logout_user(request: HttpRequest) -> None:
        """End current user session."""
        logout(request)

    @staticmethod
    def ensure_active_account(user: CustomUser) -> None:
        """Raise if account is inactive."""
        if not user.is_active:
            raise AccountInactiveError("This account has been disabled.")

    @staticmethod
    def ensure_verified_email(user: CustomUser) -> None:
        """Raise if email is not verified."""
        if not user.is_email_verified:
            raise EmailNotVerifiedError("Email verification is required.")

    @staticmethod
    def email_exists(email: str) -> bool:
        """Check if email is already registered."""
        email = CustomUser.objects.normalize_email(email)
        return CustomUser.objects.filter(email__iexact=email).exists()
    
    @staticmethod
    def resend_verification_email(user: CustomUser):
        """Resend verification email (only if not verified)."""
        if user.is_email_verified:
            return False

        # TODO: Integrate with your email backend (for now, just log it)
        logger.log_event("VERIFICATION_EMAIL_RESENT", "Verification email resent", user=user)
        return True