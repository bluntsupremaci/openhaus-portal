"""
Session Service for OpenHaus.

Handles the complete lifecycle of WiFi sessions: creation, usage tracking,
termination, quota consumption, and cleanup.
"""

from datetime import timedelta
from typing import Any

from django.db import transaction
from django.utils import timezone

from accounts.models import CustomUser
from devices.models import Device
from portal_sessions.models import WiFiSession

from openhaus_portal.core import logger
from openhaus_portal.core.constants import LogEvent
from openhaus_portal.core.exceptions import SessionError, SessionNotFoundError

from quotas.services.quotas import QuotaService
from devices.services.devices import DeviceService


class SessionService:
    """Service class for managing WiFi session lifecycle and quota integration."""

    @staticmethod
    def start_session(
        user: CustomUser,
        device: Device,
        ip_address: str | None = None,
        nas_ip: str | None = None,
        **extra: Any,
    ) -> WiFiSession:
        """Create and start a new WiFi session after successful authorization."""
        with transaction.atomic():
            DeviceService.ensure_device_allowed(device)
            QuotaService.ensure_available_quota(user, required_bytes=1)

            session = WiFiSession.objects.create(
                user=user,
                device=device,
                ip_address=ip_address,
                nas_ip=nas_ip,
                started_at=timezone.now(),
                is_active=True,
                **extra,
            )

            logger.log_session_started(user=user, device=device)
            return session

    @staticmethod
    def update_usage(
        session: WiFiSession,
        bytes_used: int,
        metadata: dict[str, Any] | None = None,
    ) -> WiFiSession:
        """Record data usage and consume quota."""
        if bytes_used <= 0:
            return session

        with transaction.atomic():
            session.refresh_from_db()

            if not session.is_active:
                raise SessionError("Cannot update usage on an inactive session.")

            session.bytes_used += bytes_used
            session.save(update_fields=["bytes_used", "updated_at"])

            QuotaService.consume_quota(
                user=session.user,
                bytes_to_consume=bytes_used,
                metadata=metadata or {},
            )

            return session

    @staticmethod
    def end_session(
        session: WiFiSession,
        reason: str = "normal_termination",
    ) -> WiFiSession:
        """Gracefully end an active session."""
        with transaction.atomic():
            session.refresh_from_db()

            if not session.is_active:
                return session

            session.ended_at = timezone.now()
            if session.ended_at and session.started_at:
                session.duration_seconds = int(
                    (session.ended_at - session.started_at).total_seconds()
                )
            session.is_active = False
            session.save(update_fields=["ended_at", "duration_seconds", "is_active", "updated_at"])

            logger.log_session_ended(user=session.user, device=session.device)
            return session
        
    @staticmethod
    def get_active_session(
        user: CustomUser | None = None,
        device: Device | None = None,
        ip_address: str | None = None,
    ) -> WiFiSession | None:
        """Retrieve the current active session for a user/device."""
        queryset = WiFiSession.objects.filter(is_active=True)

        if user:
            queryset = queryset.filter(user=user)
        if device:
            queryset = queryset.filter(device=device)
        if ip_address:
            queryset = queryset.filter(ip_address=ip_address)

        return queryset.select_related("user", "device").first()