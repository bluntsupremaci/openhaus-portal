"""
Authentication Service for OpenHaus.

Handles user identification, credential validation, and account management.
"""

from __future__ import annotations

from typing import Optional

from django.contrib.auth import authenticate, login, logout
from django.db import transaction
from django.http import HttpRequest

from accounts.models import CustomUser
from openhaus_portal.core import logger
from openhaus_portal.core.exceptions import (
    AccountInactiveError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
)
from quotas.services.quotas import QuotaService


class AuthService:
    """Service class for authentication and account management."""

    @staticmethod
    def authenticate_client(*, email: str, password: str) -> CustomUser:
        email = CustomUser.objects.normalize_email(email)
        user = authenticate(username=email, password=password)

        if user is None:
            logger.log_authentication_failure(email or "", "invalid_credentials")
            raise InvalidCredentialsError("Invalid email or password.")

        AuthService.ensure_active_account(user)
        AuthService.ensure_verified_email(user)
        return user

    @staticmethod
    def register_user(
        *,
        email: str,
        password: str,
        user_type: str = "guest",
        university_id: str | None = None,
        first_name: str = "",
        last_name: str = "",
    ) -> CustomUser:
        """Create user and grant temporary access (single place for signup rules)."""
        email = CustomUser.objects.normalize_email(email)
        if not email:
            raise ValueError("Email is required.")

        with transaction.atomic():
            user = CustomUser.objects.create_user(
                email=email,
                password=password,
                user_type=user_type,
                university_id=university_id
                if user_type in ("student", "staff")
                else None,
                first_name=first_name,
                last_name=last_name,
            )
            AuthService.grant_temporary_access(user)
            return user

    @staticmethod
    def grant_temporary_access(user: CustomUser) -> None:
        """Limited access immediately after signup (before email verification)."""
        if user.one_time_quota_granted:
            return

        try:
            with transaction.atomic():
                QuotaService.grant_welcome_gift(
                    user=user,
                    total_bytes=500 * 1024 * 1024,
                )
                logger.log_event(
                    "TEMPORARY_ACCESS_GRANTED",
                    "Temporary 500MB access granted",
                    user=user.email,
                )
        except Exception as e:
            logger.log_exception("TEMPORARY_ACCESS_ERROR", str(e), user=user.email)

    @staticmethod
    def get_user_by_email(email: str) -> Optional[CustomUser]:
        email = CustomUser.objects.normalize_email(email)
        return CustomUser.objects.filter(email__iexact=email).first()

    @staticmethod
    def login_user(*, request: HttpRequest, user: CustomUser) -> None:
        login(request, user)
        logger.log_login(user, request.META.get("REMOTE_ADDR", ""))

    @staticmethod
    def logout_user(request: HttpRequest) -> None:
        user = request.user if request.user.is_authenticated else None
        logout(request)
        if user is not None and hasattr(user, "email"):
            logger.log_logout(user)

    @staticmethod
    def ensure_active_account(user: CustomUser) -> None:
        if not user.is_active:
            raise AccountInactiveError("This account has been disabled.")

    @staticmethod
    def ensure_verified_email(user: CustomUser) -> None:
        if not user.is_email_verified:
            raise EmailNotVerifiedError("Email verification is required.")

    @staticmethod
    def email_exists(email: str) -> bool:
        email = CustomUser.objects.normalize_email(email)
        return CustomUser.objects.filter(email__iexact=email).exists()

    @staticmethod
    def resend_verification_email(user: CustomUser) -> bool:
        if user.is_email_verified:
            return False
        # TODO: wire real email backend
        logger.log_event(
            "VERIFICATION_EMAIL_RESENT",
            "Verification email resent (stub)",
            user=user.email,
        )
        return True