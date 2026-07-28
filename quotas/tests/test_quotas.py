import pytest

from openhaus_portal.core.exceptions import InsufficientQuotaError, QuotaNotFoundError
from quotas.services.quotas import QuotaService


@pytest.mark.django_db
def test_available_quota(user, quota):
    assert QuotaService.get_available_quota(user) == 100 * 1024 * 1024


@pytest.mark.django_db
def test_ensure_available_ok(user, quota):
    QuotaService.ensure_available_quota(user, required_bytes=1)


@pytest.mark.django_db
def test_ensure_available_none(user):
    with pytest.raises(QuotaNotFoundError):
        QuotaService.ensure_available_quota(user, required_bytes=1)


@pytest.mark.django_db
def test_consume_quota(user, quota):
    QuotaService.consume_quota(user, 10 * 1024 * 1024)
    assert QuotaService.get_available_quota(user) == 90 * 1024 * 1024


@pytest.mark.django_db
def test_consume_too_much(user, quota):
    with pytest.raises(InsufficientQuotaError):
        QuotaService.consume_quota(user, 200 * 1024 * 1024)
