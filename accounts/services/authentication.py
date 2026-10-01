"""Authentication Service for OpenHaus."""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.http import HttpRequest
from django.utils import timezone
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from accounts.models import CustomUser
from openhaus_portal.core import logger
from openhaus_portal.core.exceptions import (
    AccountInactiveError,
    EmailNotVerifiedError,
    InvalidCredentialsError,
)


class AuthService:
    @staticmethod
    def authenticate_client(*, email: str, password: str) -> CustomUser:
        email = CustomUser.objects.normalize_email(email)
        user = authenticate(username=email, password=password)
        if user is None:
            logger.log_authentication_failure(email or "", "invalid_credentials")
            raise InvalidCredentialsError("Invalid email or password.")
        AuthService.ensure_active_account(user)
        # Do NOT require email verification here.
        # Unverified users may log in and use signup temp access;
        # verify bonus / daily free stay gated in AccessPolicyService.
        return user  # type: ignore[return-value]

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
            from access_policy.services import AccessPolicyService

            AccessPolicyService.grant_signup_temp(user)
            return user

    @staticmethod
    def get_user_by_email(email: str) -> CustomUser | None:
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
        if user is not None and getattr(user, "email", None):
            logger.log_logout(user)  # type: ignore[arg-type]

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
    def resend_verification_email(user: CustomUser, *, request=None) -> bool:
        return AuthService.send_verification_email(user, request=request)

    @staticmethod
    def send_verification_email(user: CustomUser, *, request=None) -> bool:
        """Send email-verification link. Returns False if already verified."""
        if user.is_email_verified:
            return False

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        if request is not None:
            domain = request.get_host()
            protocol = "https" if request.is_secure() else "http"
        else:
            domain = "127.0.0.1:8000"
            protocol = "http"

        verify_url = (
            f"{protocol}://{domain}/accounts/verify-email/{uid}/{token}/"
        )

        subject = "Verify your OpenHaus email"
        message = (
            f"Hi,\n\n"
            f"Verify your OpenHaus account by opening this link "
            f"(copy the whole line):\n\n"
            f"{verify_url}\n\n"
            f"If you did not sign up, ignore this email.\n\n"
            f"— OpenHaus\n"
        )
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=False,
        )
        logger.log_event(
            "VERIFICATION_EMAIL_SENT",
            "Verification email sent",
            user=user.email,
        )
        return True

    @staticmethod
    def send_verified_welcome_email(user: CustomUser) -> None:
        """Email after successful verification (trial or free hours)."""
        from access_policy.services import AccessPolicyService

        name = (user.get_full_name() or "").strip() or user.email.split("@")[0]
        email = user.email or ""

        if AccessPolicyService.email_is_institution_domain(email):
            subject = "Welcome to OpenHaus — your campus trial is active"
            body = (
                f"Hi {name},\n\n"
                f"Your email ({email}) is verified.\n\n"
                "As a campus account, your free Premium Trial is now active. "
                "Open the dashboard to see how many days remain and any plan data.\n\n"
                "Next steps:\n"
                "  • Register your device (MAC) under Register Device\n"
                "  • Connect to campus Wi‑Fi — access is granted via membership\n\n"
                "If you did not create this account, contact support.\n\n"
                "— OpenHaus\n"
            )
        else:
            subject = "Welcome to OpenHaus — email verified"
            body = (
                f"Hi {name},\n\n"
                f"Your email ({email}) is verified.\n\n"
                "You have a one-time free access window. "
                "Open the dashboard to see time remaining.\n\n"
                "When that ends, you may get daily free minutes (if enabled), "
                "watch an ad for more time, or choose a plan.\n\n"
                "Next steps:\n"
                "  • Register your device under Register Device\n"
                "  • Connect to the network when you are on campus\n\n"
                "— OpenHaus\n"
            )

        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=True,
        )
        logger.log_event(
            "VERIFIED_WELCOME_EMAIL_SENT",
            "Post-verify welcome email sent",
            user=email,
        )

    @staticmethod
    def verify_email_token(*, uidb64: str, token: str) -> CustomUser:
        """Validate link and mark email verified. Raises ValueError on failure."""
        try:
            uid = force_str(urlsafe_base64_decode(uidb64))
            user = CustomUser.objects.get(pk=uid)
        except (TypeError, ValueError, OverflowError, CustomUser.DoesNotExist) as e:
            raise ValueError("Invalid verification link.") from e

        if user.is_email_verified:
            return user

        if not default_token_generator.check_token(user, token):
            raise ValueError("Verification link is invalid or has expired.")

        user.is_email_verified = True
        update_fields = ["is_email_verified"]
        if hasattr(user, "email_verified_at"):
            user.email_verified_at = timezone.now()
            update_fields.append("email_verified_at")
        user.save(update_fields=update_fields)
        logger.log_event(
            "EMAIL_VERIFIED",
            "Email verified via token",
            user=user.email,
        )
        try:
            AuthService.send_verified_welcome_email(user)
        except Exception:
            pass
        return user

        logger.log_event(
            "EMAIL_VERIFIED",
            "Email verified via token",
            user=user.email,
        )
        return user
