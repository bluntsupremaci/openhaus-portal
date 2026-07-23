"""
Guest Reward Service for OpenHaus.
Uses the new structured GuestConfig model.
"""

from datetime import timedelta
from django.utils import timezone
from django.db import transaction

from accounts.models import CustomUser, GuestConfig, GuestAdWatch
from quotas.services.quotas import QuotaService
from openhaus_portal.core import logger


class GuestRewardService:
    """Guest ad reward service using structured config."""

    @staticmethod
    def get_config():
        """Get guest config (only one record should exist)"""
        config, created = GuestConfig.objects.get_or_create()
        return config

    @staticmethod
    def can_watch_ad(mac_address: str) -> bool:
        """Check if user can watch another ad today."""
        config = GuestRewardService.get_config()
        if not config.ad_enabled:
            return False

        today = timezone.now().date()
        count_today = GuestAdWatch.objects.filter(
            mac_address=mac_address,
            watched_at__date=today
        ).count()

        return count_today < config.daily_limit

    @staticmethod
    def grant_ad_reward(mac_address: str):
        """Grant reward after simulated ad watch."""
        config = GuestRewardService.get_config()
        if not config.ad_enabled:
            return None

        if not GuestRewardService.can_watch_ad(mac_address):
            return None

        reward_bytes = config.reward_mb * 1024 * 1024

        try:
            with transaction.atomic():
                guest_email = f"guest.{mac_address.replace(':', '')[:12]}@temp.openhaus.local"

                user, _ = CustomUser.objects.get_or_create(
                    email=guest_email,
                    defaults={
                        "user_type": "guest",
                        "is_email_verified": True,
                        "is_active": True,
                        "password": "!",  
                    }
                )

                QuotaService.grant_daily_free_quota(
                    user=user,
                    total_bytes=reward_bytes,
                    expires_at=timezone.now() + timedelta(hours=config.expiry_hours)
                )

                GuestAdWatch.objects.create(mac_address=mac_address)

                logger.log_event(
                    "GUEST_AD_REWARD_GRANTED", 
                    f"Granted {config.reward_mb}MB to guest", 
                    user=user
                )
                return reward_bytes

        except Exception as e:
            logger.log_exception("GUEST_REWARD_ERROR", str(e))
            return None