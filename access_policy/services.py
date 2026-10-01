"""Time grants, daily free, ads — all durations from AccessPolicySettings."""

from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from django.utils import timezone

from access_policy.models import AccessGrant, AccessGrantType, AccessPolicySettings
from accounts.models import CustomUser
from memberships.services.memberships import MembershipService
from openhaus_portal.core import logger
from openhaus_portal.core.exceptions import OpenHausError


class AccessDeniedError(OpenHausError):
    """No membership and no valid time grant."""


class AccessPolicyService:
    @staticmethod
    def settings() -> AccessPolicySettings:
        return AccessPolicySettings.get_solo()

    @staticmethod
    def is_university_member(user: CustomUser) -> bool:
        return user.user_type in ("student", "staff")

    @staticmethod
    def resolve_role(user: CustomUser | None) -> str:
        if user is None:
            return "guest"
        if not user.is_active:
            return "blocked"
        if not user.is_email_verified and user.user_type != "guest":
            return "unverified"
        if MembershipService.has_active_membership(user):
            return "member"
        if AccessPolicyService.is_university_member(user):
            return "verified_student"
        if user.user_type == "guest" and user.email.endswith("@temp.openhaus.local"):
            return "guest"
        return "verified_non_student"

    @staticmethod
    def _local_today(policy: AccessPolicySettings):
        try:
            tz = ZoneInfo(policy.timezone_name)
        except Exception:
            tz = ZoneInfo("Africa/Lagos")
        return timezone.now().astimezone(tz).date()

    @staticmethod
    def get_valid_grants(user: CustomUser):
        now = timezone.now()
        return AccessGrant.objects.filter(
            user=user, is_active=True, expires_at__gt=now
        ).order_by("expires_at")

    @staticmethod
    def has_valid_time_grant(user: CustomUser) -> bool:
        return any(g.is_currently_valid for g in AccessPolicyService.get_valid_grants(user))

    @staticmethod
    def total_remaining_seconds(user: CustomUser) -> int:
        return sum(g.remaining_seconds for g in AccessPolicyService.get_valid_grants(user))

    @staticmethod
    def _create_grant(
        *,
        user: CustomUser,
        grant_type: str,
        duration_seconds: int,
        expires_at: datetime,
        data_cap_bytes: int = 0,
        grant_day=None,
        notes: str = "",
        starts_at: datetime | None = None,
    ) -> AccessGrant:
        grant = AccessGrant.objects.create(
            user=user,
            grant_type=grant_type,
            starts_at=starts_at or timezone.now(),
            expires_at=expires_at,
            duration_seconds=duration_seconds,
            data_cap_bytes=data_cap_bytes,
            grant_day=grant_day,
            notes=notes,
            is_active=True,
        )
        logger.log_event(
            "ACCESS_GRANT_CREATED",
            f"Grant {grant_type}",
            user=user.email,
            seconds=duration_seconds,
        )
        return grant

    @staticmethod
    def grant_signup_temp(user: CustomUser, *, force_start: bool = False) -> AccessGrant | None:
        policy = AccessPolicyService.settings()
        if not policy.signup_temp_enabled:
            return None
        if user.signup_temp_access_granted and not user.signup_temp_pending:
            return None

        minutes = policy.signup_temp_minutes
        duration = minutes * 60
        cap = policy.signup_temp_data_cap_mb * 1024 * 1024

        if policy.signup_timer_starts_on_first_fas and not force_start:
            user.signup_temp_access_granted = True
            user.signup_temp_pending = True
            user.save(update_fields=["signup_temp_access_granted", "signup_temp_pending"])
            return None

        now = timezone.now()
        grant = AccessPolicyService._create_grant(
            user=user,
            grant_type=AccessGrantType.SIGNUP_TEMP,
            duration_seconds=duration,
            expires_at=now + timedelta(seconds=duration),
            data_cap_bytes=cap,
            notes="Signup temporary access",
        )
        user.signup_temp_access_granted = True
        user.signup_temp_pending = False
        user.save(update_fields=["signup_temp_access_granted", "signup_temp_pending"])
        return grant

    @staticmethod
    def start_pending_signup_temp_on_fas(user: CustomUser) -> AccessGrant | None:
        if not user.signup_temp_pending:
            return None
        return AccessPolicyService.grant_signup_temp(user, force_start=True)

    @staticmethod
    def grant_verify_bonus(user: CustomUser) -> None:
        if user.signup_bonus_granted or not user.is_email_verified:
            return

        policy = AccessPolicyService.settings()

        # 1-month trial only for @bazeuniversity.edu.ng (etc.), any campus role
        if AccessPolicyService.email_is_institution_domain(user.email or ""):
            if not user.premium_trial_activated:
                MembershipService.grant_premium_trial(
                    user=user,
                    days=policy.verify_student_trial_days,
                )
                user.premium_trial_activated = True
                user.premium_trial_end_date = timezone.now() + timedelta(
                    days=policy.verify_student_trial_days
                )
        else:
            hours = policy.verify_non_student_hours
            duration = hours * 3600
            now = timezone.now()
            AccessPolicyService._create_grant(
                user=user,
                grant_type=AccessGrantType.VERIFY_BONUS,
                duration_seconds=duration,
                expires_at=now + timedelta(seconds=duration),
                notes=f"Verify bonus {hours}h (non-institution email)",
            )

        user.signup_bonus_granted = True
        user.save(
            update_fields=[
                "signup_bonus_granted",
                "premium_trial_activated",
                "premium_trial_end_date",
            ]
        )

    @staticmethod
    def ensure_daily_free(user: CustomUser) -> AccessGrant | None:
        policy = AccessPolicyService.settings()
        if not policy.daily_free_enabled or not user.is_email_verified:
            return None
        if user.user_type == "guest" and user.email.endswith("@temp.openhaus.local"):
            return None
        if MembershipService.has_active_membership(user):
            return None

        today = AccessPolicyService._local_today(policy)
        existing = AccessGrant.objects.filter(
            user=user, grant_type=AccessGrantType.DAILY_FREE, grant_day=today
        ).first()
        if existing:
            return existing if existing.is_currently_valid else None

        minutes = (
            policy.daily_free_student_minutes
            if AccessPolicyService.is_university_member(user)
            else policy.daily_free_non_student_minutes
        )
        duration = minutes * 60
        now = timezone.now()
        return AccessPolicyService._create_grant(
            user=user,
            grant_type=AccessGrantType.DAILY_FREE,
            duration_seconds=duration,
            expires_at=now + timedelta(seconds=duration),
            grant_day=today,
            notes=f"Daily free {minutes}m",
        )

    @staticmethod
    def grant_ad_reward(user: CustomUser) -> AccessGrant | None:
        policy = AccessPolicyService.settings()
        if not policy.ad_reward_enabled:
            return None

        today = AccessPolicyService._local_today(policy)
        used = AccessGrant.objects.filter(
            user=user, grant_type=AccessGrantType.AD_REWARD, grant_day=today
        ).count()
        if used >= policy.ad_daily_limit:
            return None

        duration = policy.ad_reward_minutes * 60
        cap = policy.ad_reward_data_cap_mb * 1024 * 1024
        now = timezone.now()
        wall = now + timedelta(hours=policy.ad_grant_expiry_hours)
        expire = min(wall, now + timedelta(seconds=duration))

        return AccessPolicyService._create_grant(
            user=user,
            grant_type=AccessGrantType.AD_REWARD,
            duration_seconds=duration,
            expires_at=expire,
            data_cap_bytes=cap,
            grant_day=today,
            notes="Ad reward",
        )

    @staticmethod
    def ensure_access_for_authorization(user: CustomUser) -> None:
        AccessPolicyService.start_pending_signup_temp_on_fas(user)
        AccessPolicyService.ensure_daily_free(user)

        if MembershipService.has_active_membership(user):
            return
        if AccessPolicyService.has_valid_time_grant(user):
            return
        raise AccessDeniedError(
            "No active plan or free access window. "
            "Verify email, use daily free, watch an ad, or subscribe."
        )

    @staticmethod
    def email_is_institution_domain(email: str) -> bool:
        """True if email uses an allowed campus domain (Admin: student_email_domains)."""
        policy = AccessPolicyService.settings()
        email = (email or "").strip().lower()
        if "@" not in email:
            return False
        domain = email.rsplit("@", 1)[-1]
        allowed = [
            d.strip().lower().lstrip("@")
            for d in (policy.student_email_domains or "").split(",")
            if d.strip()
        ]
        return domain in allowed

    @staticmethod
    def domain_allowed_for_student(email: str) -> bool:
        """Alias used at signup (student + staff)."""
        return AccessPolicyService.email_is_institution_domain(email)

    @staticmethod
    def email_is_student_domain(user: CustomUser) -> bool:
        return AccessPolicyService.email_is_institution_domain(user.email or "")
