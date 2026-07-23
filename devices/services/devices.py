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
from openhaus_portal.core.constants import LogEvent
from openhaus_portal.core.exceptions import (
    DeviceAlreadyRegisteredError,
    DeviceBlockedError,
    DeviceNotFoundError,
)


class DeviceService:
    """Service class for all device-related operations."""

    # ============================================================================
    # Query Methods
    # ============================================================================

    @staticmethod
    def get_device(mac_address: str) -> Device:
        """Retrieve device by MAC address.

        Raises:
            DeviceNotFoundError
        """
        device = (
            Device.objects.select_related("user")
            .filter(mac_address__iexact=mac_address)
            .first()
        )

        if device is None:
            raise DeviceNotFoundError(f"Device '{mac_address}' was not found.")

        return device

    @staticmethod
    def device_exists(mac_address: str) -> bool:
        """Check if a device with this MAC is already registered."""
        return Device.objects.filter(mac_address__iexact=mac_address).exists()

    @staticmethod
    def get_user_devices(user: CustomUser):
        """Return all devices owned by a user."""
        return Device.objects.filter(user=user)

    @staticmethod
    def get_active_devices(user: CustomUser):
        """Return non-blocked devices for a user."""
        return Device.objects.filter(user=user, is_blocked=False)

    # ============================================================================
    # Lifecycle Management
    # ============================================================================

    @staticmethod
    def register_device(
        *,
        owner: CustomUser,
        mac_address: str,
        hostname: str = "",
        platform: str = "",
    ) -> Device:
        """Register a new device for a user.

        Raises:
            DeviceAlreadyRegisteredError
        """
        try:
            device = Device.objects.create(
                user=owner,
                mac_address=mac_address.upper(),
                hostname=hostname.strip(),
                platform=platform.strip(),
            )

            logger.log_device_registered(device=device)
            return device

        except IntegrityError as exc:
            raise DeviceAlreadyRegisteredError(
                f"Device with MAC '{mac_address}' is already registered."
            ) from exc

    @staticmethod
    def update_last_seen(device: Device) -> None:
        """Update device's last activity timestamp."""
        device.last_seen = timezone.now()
        device.save(update_fields=["last_seen"])

    @staticmethod
    def trust_device(device: Device) -> Device:
        """Mark device as trusted."""
        device.is_trusted = True
        device.save(update_fields=["is_trusted"])
        return device

    @staticmethod
    def untrust_device(device: Device) -> Device:
        """Remove trusted status."""
        device.is_trusted = False
        device.save(update_fields=["is_trusted"])
        return device

    @staticmethod
    def block_device(device: Device) -> Device:
        """Block device from network access."""
        device.is_blocked = True
        device.save(update_fields=["is_blocked"])
        logger.log_device_blocked(device=device)
        return device

    @staticmethod
    def unblock_device(device: Device) -> Device:
        """Unblock a device."""
        device.is_blocked = False
        device.save(update_fields=["is_blocked"])
        logger.log_device_unblocked(device=device)
        return device

    # ============================================================================
    # Validation
    # ============================================================================

    @staticmethod
    def ensure_device_allowed(device: Device) -> Device:
        """Verify device is allowed on the network.

        Raises:
            DeviceBlockedError
        """
        if device.is_blocked:
            raise DeviceBlockedError(f"Device '{device.mac_address}' is blocked.")
        return device

    @staticmethod
    def delete_device(device: Device) -> None:
        """Permanently delete a device record."""
        device.delete()