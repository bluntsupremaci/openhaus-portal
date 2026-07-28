"""
Session Service for OpenHaus.

Handles WiFi session lifecycle: creation, usage tracking, termination, quota.
"""

from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from accounts.models import CustomUser
from devices.models import Device
from devices.services.devices import DeviceService
from openhaus_portal.core import logger
from openhaus_portal.core.exceptions import SessionError
from portal_sessions.models import WiFiSession
from quotas.services.quotas import QuotaService


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

            # End any existing active sessions for this device (one active per device).
            active = WiFiSession.objects.select_for_update().filter(
                device=device,
                is_active=True,
            )
            now = timezone.now()
            for old in active:
                old.ended_at = now
                if old.started_at:
                    old.duration_seconds = int((now - old.started_at).total_seconds())
                old.is_active = False
                old.save(
                    update_fields=[
                        "ended_at",
                        "duration_seconds",
                        "is_active",
                        "updated_at",
                    ]
                )
                logger.log_session_ended(user=old.user, device=old.device)

            session = WiFiSession.objects.create(
                user=user,
                device=device,
                ip_address=ip_address,
                nas_ip=nas_ip,
                started_at=now,
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
        if bytes_used <= 0:
            return session

        with transaction.atomic():
            session = WiFiSession.objects.select_for_update().get(pk=session.pk)

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
        with transaction.atomic():
            session = WiFiSession.objects.select_for_update().get(pk=session.pk)

            if not session.is_active:
                return session

            session.ended_at = timezone.now()
            if session.ended_at and session.started_at:
                session.duration_seconds = int(
                    (session.ended_at - session.started_at).total_seconds()
                )
            session.is_active = False
            session.save(
                update_fields=[
                    "ended_at",
                    "duration_seconds",
                    "is_active",
                    "updated_at",
                ]
            )

            logger.log_session_ended(user=session.user, device=session.device)
            return session

    @staticmethod
    def get_active_session(
        user: CustomUser | None = None,
        device: Device | None = None,
        ip_address: str | None = None,
    ) -> WiFiSession | None:
        queryset = WiFiSession.objects.filter(is_active=True)

        if user:
            queryset = queryset.filter(user=user)
        if device:
            queryset = queryset.filter(device=device)
        if ip_address:
            queryset = queryset.filter(ip_address=ip_address)

        return queryset.select_related("user", "device").first()
