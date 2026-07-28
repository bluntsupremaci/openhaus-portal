"""Post-verify one-time bonus via AccessPolicyService."""

from django.db.models.signals import post_save
from django.dispatch import receiver

from accounts.models import CustomUser
from openhaus_portal.core import logger


@receiver(post_save, sender=CustomUser)
def on_email_verified(sender, instance: CustomUser, **kwargs):
    if not instance.is_email_verified or instance.signup_bonus_granted:
        return
    try:
        from access_policy.services import AccessPolicyService

        AccessPolicyService.grant_verify_bonus(instance)
        logger.log_event("SIGNUP_BONUS_GRANTED", "Verify bonus applied", user=instance.email)
    except Exception as e:
        logger.log_exception("VERIFY_BONUS_ERROR", str(e), user=instance.email)
