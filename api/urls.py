"""
API URLs for OpenHaus.

Mainly contains the FAS (Forward Authentication Service) endpoint used by openNDS.
"""

from django.urls import path

from .views import FASView

app_name = "api"

urlpatterns = [
    # Main FAS endpoint used by openNDS captive portal
    path("fas/", FASView.as_view(), name="fas"),
    
    # Optional alias (some setups use /fas/auth/)
    path("fas/auth/", FASView.as_view(), name="fas_auth"),
]