"""
Device Service for OpenHaus.

Business logic for device registration, validation, and lifecycle management.
"""

from __future__ import annotations

from django.db import IntegrityError
from django.utils import timezone

from accounts.models import CustomUser
from devices.models import Device
from openhaus_portal.core import logger
from openhaus_portal.core.exceptions import (
    DeviceAlreadyRegisteredError,
    DeviceBlockedError,
    DeviceNotFoundError,
)


class DeviceService:
    """Service class for all device-related operations."""

    @staticmethod
    def normalize_mac(mac_address: str) -> str:
        return (mac_address or "").strip().upper()

    @staticmethod
    def get_device(mac_address: str) -> Device:
        mac = DeviceService.normalize_mac(mac_address)
        device = (
            Device.objects.select_related("user")
            .filter(mac_address__iexact=mac)
            .first()
        )
        if device is None:
            raise DeviceNotFoundError(f"Device '{mac}' was not found.")
        return device

    @staticmethod
    def device_exists(mac_address: str) -> bool:
        mac = DeviceService.normalize_mac(mac_address)
        return Device.objects.filter(mac_address__iexact=mac).exists()

    @staticmethod
    def get_user_devices(user: CustomUser):
        return Device.objects.filter(user=user)

    @staticmethod
    def get_active_devices(user: CustomUser):
        return Device.objects.filter(user=user, is_blocked=False)

    @staticmethod
    def register_device(
        *,
        owner: CustomUser,
        mac_address: str,
        hostname: str = "",
        platform: str = "",
    ) -> Device:
        mac = DeviceService.normalize_mac(mac_address)
        try:
            device = Device.objects.create(
                user=owner,
                mac_address=mac,
                hostname=(hostname or "").strip() or None,
                platform=(platform or "").strip() or None,
            )
            logger.log_device_registered(device=device)
            return device
        except IntegrityError as exc:
            raise DeviceAlreadyRegisteredError(
                f"Device with MAC '{mac}' is already registered."
            ) from exc

    @staticmethod
    def get_or_register_device(
        *,
        owner: CustomUser,
        mac_address: str,
        hostname: str = "",
        platform: str = "",
    ) -> Device:
        """
        Return existing device for MAC, or register it to owner.

        Raises DeviceAlreadyRegisteredError if MAC belongs to another user.
        """
        mac = DeviceService.normalize_mac(mac_address)
        existing = (
            Device.objects.select_related("user")
            .filter(mac_address__iexact=mac)
            .first()
        )
        if existing is not None:
            if existing.user_id != owner.pk:
                raise DeviceAlreadyRegisteredError(
                    f"Device with MAC '{mac}' is already registered."
                )
            return existing
        return DeviceService.register_device(
            owner=owner,
            mac_address=mac,
            hostname=hostname,
            platform=platform,
        )

    @staticmethod
    def update_last_seen(device: Device) -> None:
        device.last_seen = timezone.now()
        device.save(update_fields=["last_seen", "updated_at"])

    @staticmethod
    def trust_device(device: Device) -> Device:
        device.is_trusted = True
        device.save(update_fields=["is_trusted", "updated_at"])
        return device

    @staticmethod
    def untrust_device(device: Device) -> Device:
        device.is_trusted = False
        device.save(update_fields=["is_trusted", "updated_at"])
        return device

    @staticmethod
    def block_device(device: Device) -> Device:
        device.is_blocked = True
        device.save(update_fields=["is_blocked", "updated_at"])
        logger.log_device_blocked(device=device)
        return device

    @staticmethod
    def unblock_device(device: Device) -> Device:
        device.is_blocked = False
        device.save(update_fields=["is_blocked", "updated_at"])
        logger.log_device_unblocked(device=device)
        return device

    @staticmethod
    def ensure_device_allowed(device: Device) -> Device:
        if device.is_blocked:
            raise DeviceBlockedError(f"Device '{device.mac_address}' is blocked.")
        return device

    @staticmethod
    def delete_device(device: Device) -> None:
        device.delete()