"""
Signals for CustomUser model - handles post-verification bonuses and cleanup.
"""

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from .models import CustomUser
from memberships.services.memberships import MembershipService
from quotas.services.quotas import QuotaService
from openhaus_portal.core import logger
from openhaus_portal.core.exceptions import ActiveMembershipExistsError


@receiver(post_save, sender=CustomUser)
def grant_signup_bonuses(sender, instance: CustomUser, created, **kwargs):
    """
    Automatically grant signup bonuses when email is verified.
    Runs only once per user.
    """
    if not instance.is_email_verified or instance.signup_bonus_granted:
        return

    try:
        with transaction.atomic():
            if instance.is_university_member:
                if not instance.premium_trial_activated:
                    MembershipService.grant_premium_trial(user=instance, months=1)
                    instance.premium_trial_activated = True
                    instance.premium_trial_end_date = timezone.now() + timezone.timedelta(days=30)
            else:
                if not instance.one_time_quota_granted:
                    QuotaService.grant_welcome_gift(user=instance, total_bytes=5 * 1024 * 1024 * 1024)

            instance.signup_bonus_granted = True
            instance.save(update_fields=[
                'signup_bonus_granted',
                'premium_trial_activated',
                'premium_trial_end_date'
            ])

            logger.log_event("SIGNUP_BONUS_GRANTED", "Signup bonus granted", user=instance)

    except ActiveMembershipExistsError:
        instance.signup_bonus_granted = True
        instance.save(update_fields=['signup_bonus_granted'])
        logger.log_event("SIGNUP_BONUS_SKIPPED", "User already has active membership", user=instance)
    except Exception as e:
        logger.log_exception("SIGNUP_BONUS_ERROR", str(e), user=instance)