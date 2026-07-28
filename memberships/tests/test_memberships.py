import pytest

from memberships.services.memberships import MembershipService
from openhaus_portal.core.exceptions import MembershipNotFoundError


@pytest.mark.django_db
def test_has_active_membership(user, active_membership):
    assert MembershipService.has_active_membership(user) is True


@pytest.mark.django_db
def test_get_active_membership(user, active_membership):
    m = MembershipService.get_active_membership(user)
    assert m.pk == active_membership.pk


@pytest.mark.django_db
def test_get_active_membership_missing(user):
    with pytest.raises(MembershipNotFoundError):
        MembershipService.get_active_membership(user)


@pytest.mark.django_db
def test_membership_summary_empty(user):
    summary = MembershipService.get_membership_summary(user)
    assert summary["has_membership"] is False
