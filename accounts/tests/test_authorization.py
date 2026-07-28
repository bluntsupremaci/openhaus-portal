import pytest

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


@pytest.mark.django_db
def test_authorize_guest_quota_only(guest_user, guest_device, guest_quota):
    result = AuthorizationService.authorize_network_access(
        mac_address=guest_device.mac_address,
    )
    assert result["action"] == "allow"
    assert result["user_type"] == "guest"


@pytest.mark.django_db
def test_authorize_student_without_membership(user, device, quota):
    with pytest.raises(OpenHausError):
        AuthorizationService.authorize_network_access(mac_address=device.mac_address)


@pytest.mark.django_db
def test_can_access_network(user, device, active_membership, quota):
    AuthorizationService.can_access_network(user=user, device=device)
