"""
Session Service for OpenHaus.

WiFi session lifecycle. Quota is required only when the user has
active data allocations (e.g. membership); time-grant-only users skip it.
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
    """Manage WiFi session lifecycle."""

    @staticmethod
    def start_session(
        user: CustomUser,
        device: Device,
        ip_address: str | None = None,
        nas_ip: str | None = None,
        **extra: Any,
    ) -> WiFiSession:
        with transaction.atomic():
            DeviceService.ensure_device_allowed(device)

            # Data quota only if user already has allocations (membership path).
            # Time-grant users (signup / daily / ads) may have no QuotaAllocation.
            if QuotaService.get_active_allocations(user).exists():
                QuotaService.ensure_available_quota(user, required_bytes=1)

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

            if QuotaService.get_active_allocations(session.user).exists():
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

    @staticmethod
    def get_user_sessions(user: CustomUser, limit: int = 20) -> list[WiFiSession]:
        """Recent sessions for the session details UI (active + history)."""
        return list(
            WiFiSession.objects.filter(user=user)
            .select_related("user", "device")
            .order_by("-started_at")[:limit]
        )
