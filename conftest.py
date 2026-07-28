"""Shared pytest fixtures — verify signal silenced so tests control grants."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.utils import timezone

from devices.models import Device
from memberships.models import MembershipPlan, MembershipStatus, UserMembership
from quotas.models import QuotaAllocation, QuotaType

User = get_user_model()


@pytest.fixture(autouse=True)
def _silence_verify_signal():
    """Unit tests own membership / grants; do not auto-fire verify bonus."""
    from accounts.models import CustomUser

    # Support either signal function name
    try:
        from accounts.signals import on_email_verified as _sig
    except ImportError:
        try:
            from accounts.signals import grant_signup_bonuses as _sig
        except ImportError:
            yield
            return

    post_save.disconnect(_sig, sender=CustomUser)
    yield
    post_save.connect(_sig, sender=CustomUser)


@pytest.fixture
def policy(db):
    from access_policy.models import AccessPolicySettings

    return AccessPolicySettings.get_solo()


@pytest.fixture
def user(db):
    """Verified student with no auto trial / no membership unless fixture adds it."""
    return User.objects.create_user(
        email="student@example.com",
        password="test-pass-123",
        user_type="student",
        is_email_verified=True,
        is_active=True,
        signup_bonus_granted=True,
        premium_trial_activated=True,
        signup_temp_access_granted=True,
        signup_temp_pending=False,
    )


@pytest.fixture
def unverified_user(db):
    return User.objects.create_user(
        email="new@example.com",
        password="test-pass-123",
        user_type="guest",
        is_email_verified=False,
        is_active=True,
    )


@pytest.fixture
def guest_user(db):
    u = User.objects.create_user(
        email="guest.aabbccddeeff@temp.openhaus.local",
        password="unused-pass-123",
        user_type="guest",
        is_email_verified=True,
        is_active=True,
    )
    u.set_unusable_password()
    u.save(update_fields=["password"])
    return u


@pytest.fixture
def device(user):
    return Device.objects.create(
        user=user,
        mac_address="AA:BB:CC:DD:EE:FF",
        hostname="test-phone",
        platform="iOS",
    )


@pytest.fixture
def guest_device(guest_user):
    return Device.objects.create(
        user=guest_user,
        mac_address="11:22:33:44:55:66",
        hostname="guest-phone",
    )


@pytest.fixture
def plan(db):
    plan, _ = MembershipPlan.objects.get_or_create(
        slug="premium-trial",
        defaults={
            "name": "Premium Trial",
            "duration_days": 30,
            "included_quota_gb": 50,
            "max_devices": 5,
            "price": 0,
            "is_active": True,
        },
    )
    return plan


@pytest.fixture
def active_membership(user, plan):
    now = timezone.now()
    return UserMembership.objects.create(
        user=user,
        plan=plan,
        status=MembershipStatus.ACTIVE,
        start_date=now,
        end_date=now + timedelta(days=30),
    )


@pytest.fixture
def quota(user):
    return QuotaAllocation.objects.create(
        user=user,
        quota_type=QuotaType.MEMBERSHIP,
        total_bytes=100 * 1024 * 1024,
        used_bytes=0,
        granted_at=timezone.now(),
        expires_at=timezone.now() + timedelta(days=7),
        is_active=True,
    )


@pytest.fixture
def guest_quota(guest_user):
    return QuotaAllocation.objects.create(
        user=guest_user,
        quota_type=QuotaType.FREE_DAILY,
        total_bytes=50 * 1024 * 1024,
        used_bytes=0,
        granted_at=timezone.now(),
        expires_at=timezone.now() + timedelta(hours=24),
        is_active=True,
    )
