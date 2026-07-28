"""
API URLs for OpenHaus.

Mainly contains the FAS (Forward Authentication Service) endpoint used by openNDS.
"""

from django.urls import path

from .views import FASView

app_name = "api"

urlpatterns = [
    path("fas/", FASView.as_view(), name="fas"),
    path("fas/auth/", FASView.as_view(), name="fas_auth"),
]