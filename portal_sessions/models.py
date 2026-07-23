"""
WiFi Session model for OpenHaus.

Tracks active and historical network sessions for auditing,
quota consumption, and analytics.
"""

import uuid

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from accounts.models import CustomUser
from devices.models import Device


class WiFiSession(models.Model):
    """Represents a single Wi-Fi connection session."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="wifi_sessions",
    )

    device = models.ForeignKey(
        Device,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="wifi_sessions",
    )

    # Session timing
    started_at = models.DateTimeField(_("start time"), default=timezone.now)
    ended_at = models.DateTimeField(_("end time"), null=True, blank=True)

    # Usage tracking
    bytes_used = models.BigIntegerField(_("bytes used"), default=0)
    duration_seconds = models.BigIntegerField(_("duration seconds"), default=0)

    # Network info from openNDS
    mac_address = models.CharField(max_length=17, db_index=True, blank=True)
    ip_address = models.GenericIPAddressField(_("IP address"), blank=True, null=True)
    nas_ip = models.GenericIPAddressField(_("NAS IP"), blank=True, null=True)

    is_active = models.BooleanField(_("active session"), default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("WiFi Session")
        verbose_name_plural = _("WiFi Sessions")
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["device", "is_active"]),
            models.Index(fields=["mac_address"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.email} - {self.started_at}"

    def end_session(self) -> None:
        """Properly close an active session."""
        if self.is_active:
            self.ended_at = timezone.now()
            if self.ended_at and self.started_at:
                self.duration_seconds = int((self.ended_at - self.started_at).total_seconds())
            self.is_active = False
            self.save(update_fields=["ended_at", "duration_seconds", "is_active", "updated_at"])

    @property
    def is_ongoing(self) -> bool:
        """True if session is still active."""
        return self.is_active