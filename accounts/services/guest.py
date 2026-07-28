"""
Guest Reward Service for OpenHaus.
Uses the structured GuestConfig model and links MAC → Device for FAS.
"""

from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from accounts.models import CustomUser, GuestAdWatch, GuestConfig
from devices.services.devices import DeviceService
from openhaus_portal.core import logger
from openhaus_portal.core.exceptions import DeviceAlreadyRegisteredError
from quotas.services.quotas import QuotaService


class GuestRewardService:
    """Guest ad reward service using structured config."""

    @staticmethod
    def get_config() -> GuestConfig:
        config, _ = GuestConfig.objects.get_or_create()
        return config

    @staticmethod
    def can_watch_ad(mac_address: str) -> bool:
        config = GuestRewardService.get_config()
        if not config.ad_enabled:
            return False

        mac = DeviceService.normalize_mac(mac_address)
        today = timezone.now().date()
        count_today = GuestAdWatch.objects.filter(
            mac_address=mac,
            watched_at__date=today,
        ).count()
        return count_today < config.daily_limit

    @staticmethod
    def grant_ad_reward(mac_address: str) -> int | None:
        """Grant reward after ad watch; ensure Device exists for FAS MAC lookup."""
        config = GuestRewardService.get_config()
        if not config.ad_enabled:
            return None

        mac = DeviceService.normalize_mac(mac_address)
        if not mac or mac == "UNKNOWN":
            return None

        if not GuestRewardService.can_watch_ad(mac):
            return None

        reward_bytes = config.reward_mb * 1024 * 1024

        try:
            with transaction.atomic():
                guest_email = (
                    f"guest.{mac.replace(':', '').replace('-', '')[:12].lower()}"
                    f"@temp.openhaus.local"
                )

                user, created = CustomUser.objects.get_or_create(
                    email=guest_email,
                    defaults={
                        "user_type": "guest",
                        "is_email_verified": True,
                        "is_active": True,
                    },
                )
                if created:
                    user.set_unusable_password()
                    user.save(update_fields=["password"])

                try:
                    DeviceService.get_or_register_device(
                        owner=user,
                        mac_address=mac,
                        hostname="guest-device",
                        platform="captive-portal",
                    )
                except DeviceAlreadyRegisteredError:
                    # MAC already owned — still grant quota to that owner if same flow fails
                    device = DeviceService.get_device(mac)
                    user = device.user

                QuotaService.grant_daily_free_quota(
                    user=user,
                    total_bytes=reward_bytes,
                    expires_at=timezone.now() + timedelta(hours=config.expiry_hours),
                )

                GuestAdWatch.objects.create(mac_address=mac)

                logger.log_event(
                    "GUEST_AD_REWARD_GRANTED",
                    f"Granted {config.reward_mb}MB to guest",
                    user=user.email,
                    mac=mac,
                )
                return reward_bytes

        except Exception as e:
            logger.log_exception("GUEST_REWARD_ERROR", str(e), mac=mac)
            return None