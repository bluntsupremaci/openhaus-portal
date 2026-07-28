import pytest
from django.test import Client


@pytest.mark.django_db
def test_fas_missing_mac():
    client = Client()
    response = client.get("/api/fas/?format=json")
    assert response.status_code == 400
    assert response.json()["action"] == "block"


@pytest.mark.django_db
def test_fas_unknown_device():
    client = Client()
    response = client.get("/api/fas/?format=json&clientmac=00:11:22:33:44:55")
    assert response.status_code == 403
    assert response.json()["action"] == "block"


@pytest.mark.django_db
def test_fas_allow_json(user, device, active_membership, quota):
    client = Client()
    response = client.get(
        f"/api/fas/?format=json&clientmac={device.mac_address}&clientip=10.0.0.8"
    )
    assert response.status_code == 200
    data = response.json()
    assert data["action"] == "allow"
    assert data["username"] == user.email
    assert "session_id" in data
    assert "quota_remaining" in data
    assert "grant_seconds_remaining" in data


@pytest.mark.django_db
def test_fas_accepts_client_mac_alias(user, device, active_membership, quota):
    client = Client()
    response = client.get(f"/api/fas/?format=json&client_mac={device.mac_address}")
    assert response.status_code == 200
    assert response.json()["action"] == "allow"
