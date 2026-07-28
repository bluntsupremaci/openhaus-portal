import pytest

from access_policy.services import AccessDeniedError
from accounts.services.authorization import AuthorizationService
from openhaus_portal.core.exceptions import OpenHausError


@pytest.mark.django_db
def test_authorize_success(user, device, active_membership, quota):
    result = AuthorizationService.authorize_network_access(
        mac_address=device.mac_address,
        ip_address="10.0.0.5",
    )
    assert result["action"] == "allow"
    assert result["username"] == user.email
    assert result["session_id"]
    assert "quota_remaining" in result
    assert "grant_seconds_remaining" in result


@pytest.mark.django_db
def test_authorize_guest_with_ad_grant(guest_user, guest_device, policy):
    from access_policy.services import AccessPolicyService

    grant = AccessPolicyService.grant_ad_reward(guest_user)
    assert grant is not None
    result = AuthorizationService.authorize_network_access(
        mac_address=guest_device.mac_address,
    )
    assert result["action"] == "allow"


@pytest.mark.django_db
def test_authorize_student_without_membership(user, device, policy):
    """No membership and daily free off → deny."""
    policy.daily_free_enabled = False
    policy.save(update_fields=["daily_free_enabled"])
    user.access_grants.all().delete()

    with pytest.raises((AccessDeniedError, OpenHausError)):
        AuthorizationService.authorize_network_access(mac_address=device.mac_address)


@pytest.mark.django_db
def test_can_access_network(user, device, active_membership, quota):
    AuthorizationService.can_access_network(user=user, device=device)
