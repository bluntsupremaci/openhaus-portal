"""Guest / ad rewards → AccessPolicy time grants + device link."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from access_policy.services import AccessPolicyService
from accounts.models import CustomUser, GuestAdWatch
from devices.services.devices import DeviceService
from openhaus_portal.core import logger
from openhaus_portal.core.exceptions import DeviceAlreadyRegisteredError


class GuestRewardService:
    @staticmethod
    def can_watch_ad(mac_address: str) -> bool:
        policy = AccessPolicyService.settings()
        if not policy.ad_reward_enabled:
            return False
        mac = DeviceService.normalize_mac(mac_address)
        if not mac or mac == "UNKNOWN":
            return False
        today = timezone.now().date()
        count = GuestAdWatch.objects.filter(
            mac_address=mac, watched_at__date=today
        ).count()
        return count < policy.ad_daily_limit

    @staticmethod
    def grant_ad_reward(
        mac_address: str,
        hostname: str | None = None,
    ) -> int | None:
        """
        Grant ad reward time for a device MAC.
        Returns duration in seconds, or None if denied / error.
        """
        mac = DeviceService.normalize_mac(mac_address)
        if not mac or mac == "UNKNOWN":
            return None
        if not GuestRewardService.can_watch_ad(mac):
            return None

        display_name = (hostname or "").strip()[:64] or "guest-device"

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
                        hostname=display_name,
                        platform="captive-portal",
                    )
                except DeviceAlreadyRegisteredError:
                    device = DeviceService.get_device(mac)
                    user = getattr(device, "owner", None) or device.user
                    # Upgrade placeholder name if we now know a real one
                    current = (getattr(device, "hostname", None) or "").strip()
                    if display_name != "guest-device" and (
                        not current or current == "guest-device"
                    ):
                        device.hostname = display_name
                        device.save(update_fields=["hostname"])

                grant = AccessPolicyService.grant_ad_reward(user)
                if grant is None:
                    return None

                GuestAdWatch.objects.create(mac_address=mac)
                logger.log_event(
                    "GUEST_AD_REWARD_GRANTED",
                    "Ad reward granted",
                    user=user.email,
                    mac=mac,
                    hostname=display_name,
                    seconds=grant.duration_seconds,
                )
                return int(grant.duration_seconds)
        except Exception as e:
            logger.log_exception("GUEST_REWARD_ERROR", str(e), mac=mac)
            return None
