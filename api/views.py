"""
Forward Authentication Service (FAS) View for openNDS.

Thin HTTP adapter — all business logic lives in services (ADR-0002).
"""

from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from api.services.fas import FASService


@method_decorator(csrf_exempt, name="dispatch")
class FASView(View):
    """
    openNDS FAS entrypoint.

    GET/POST: authorize client and redirect to authaction when present.
    Append ?format=json for machine-readable lab debugging.
    """

    def get(self, request):
        return FASService.handle(request)

    def post(self, request):
        return FASService.handle(request)
