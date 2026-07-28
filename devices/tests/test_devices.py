import pytest

from devices.services.devices import DeviceService
from openhaus_portal.core.exceptions import (
    DeviceAlreadyRegisteredError,
    DeviceBlockedError,
    DeviceNotFoundError,
)


@pytest.mark.django_db
def test_normalize_mac():
    assert DeviceService.normalize_mac(" aa:bb:cc:dd:ee:ff ") == "AA:BB:CC:DD:EE:FF"


@pytest.mark.django_db
def test_get_device(device):
    found = DeviceService.get_device("aa:bb:cc:dd:ee:ff")
    assert found.pk == device.pk


@pytest.mark.django_db
def test_get_device_missing():
    with pytest.raises(DeviceNotFoundError):
        DeviceService.get_device("00:00:00:00:00:00")


@pytest.mark.django_db
def test_get_or_register_device(user):
    d1 = DeviceService.get_or_register_device(
        owner=user,
        mac_address="AB:CD:EF:12:34:56",
        hostname="phone",
    )
    d2 = DeviceService.get_or_register_device(
        owner=user,
        mac_address="ab:cd:ef:12:34:56",
    )
    assert d1.pk == d2.pk


@pytest.mark.django_db
def test_get_or_register_other_owner(user, guest_user, device):
    with pytest.raises(DeviceAlreadyRegisteredError):
        DeviceService.get_or_register_device(
            owner=guest_user,
            mac_address=device.mac_address,
        )


@pytest.mark.django_db
def test_ensure_device_allowed_blocked(device):
    device.is_blocked = True
    device.save(update_fields=["is_blocked"])
    with pytest.raises(DeviceBlockedError):
        DeviceService.ensure_device_allowed(device)
