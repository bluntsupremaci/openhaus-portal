"""
Signals for CustomUser — post-verification bonuses.
"""

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from memberships.services.memberships import MembershipService
from openhaus_portal.core import logger
from openhaus_portal.core.exceptions import ActiveMembershipExistsError
from quotas.services.quotas import QuotaService

from .models import CustomUser


@receiver(post_save, sender=CustomUser)
def grant_signup_bonuses(sender, instance: CustomUser, created, **kwargs):
    """
    Grant signup bonuses once when email becomes verified.
    Students/staff: premium trial. Others: welcome gift if not already granted.
    """
    if not instance.is_email_verified or instance.signup_bonus_granted:
        return

    try:
        with transaction.atomic():
            if instance.is_university_member:
                if not instance.premium_trial_activated:
                    MembershipService.grant_premium_trial(user=instance, months=1)
                    instance.premium_trial_activated = True
                    instance.premium_trial_end_date = timezone.now() + timezone.timedelta(
                        days=30
                    )
            else:
                # Welcome gift only if temporary access did not already set the flag
                if not instance.one_time_quota_granted:
                    QuotaService.grant_welcome_gift(
                        user=instance,
                        total_bytes=500 * 1024 * 1024,
                    )

            instance.signup_bonus_granted = True
            instance.save(
                update_fields=[
                    "signup_bonus_granted",
                    "premium_trial_activated",
                    "premium_trial_end_date",
                ]
            )
            logger.log_event(
                "SIGNUP_BONUS_GRANTED",
                "Signup bonus granted",
                user=instance.email,
            )

    except ActiveMembershipExistsError:
        instance.signup_bonus_granted = True
        instance.save(update_fields=["signup_bonus_granted"])
        logger.log_event(
            "SIGNUP_BONUS_SKIPPED",
            "User already has active membership",
            user=instance.email,
        )
    except Exception as e:
        logger.log_exception("SIGNUP_BONUS_ERROR", str(e), user=instance.email)