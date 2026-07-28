"""
Device model for OpenHaus.

Represents client devices linked to users for MAC-based authentication
and session tracking in the captive portal.
"""

import uuid

from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from accounts.models import CustomUser


class Device(models.Model):
    """Wi-Fi device owned by a user."""

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
    )

    user = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name="devices",
        help_text="Owner of this device",
    )

    mac_address = models.CharField(
        _("MAC Address"),
        max_length=17,
        unique=True,
        db_index=True,
        validators=[
            RegexValidator(
                regex=r"^([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})$",
                message=_("Enter a valid MAC address (e.g., AA:BB:CC:DD:EE:FF)"),
            )
        ],
        help_text="Unique hardware address (XX:XX:XX:XX:XX:XX)",
    )

    hostname = models.CharField(
        _("hostname"),
        max_length=100,
        blank=True,
        null=True,
        help_text="Device hostname if available",
    )

    platform = models.CharField(
        _("platform"),
        max_length=50,
        blank=True,
        null=True,
        help_text="e.g., Android, iOS, Windows, macOS",
    )

    last_seen = models.DateTimeField(
        _("last seen"),
        auto_now=True,
        help_text="Last time this device was detected on the network",
    )

    is_trusted = models.BooleanField(
        _("trusted device"),
        default=True,
        help_text="Trusted devices can bypass some restrictions",
    )

    is_blocked = models.BooleanField(
        _("blocked"),
        default=False,
        help_text="Administratively blocked from network",
    )

    created_at = models.DateTimeField(_("created at"), auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("device")
        verbose_name_plural = _("devices")
        ordering = ["-last_seen", "user"]
        indexes = [
            models.Index(fields=["mac_address"]),
            models.Index(fields=["user", "last_seen"]),
            models.Index(fields=["is_blocked"]),
        ]

    def __str__(self) -> str:
        return f"{self.hostname or self.mac_address} ({self.user.email})"

    def clean(self) -> None:
        """Additional model validation if needed."""
        super().clean()
