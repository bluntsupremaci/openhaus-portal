"""
Forward Authentication Service (FAS) View for openNDS.
Thin HTTP adapter — business logic in FASService.
"""

from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from api.services.fas import FASService


def _normalize_client_mac(raw) -> str:
    if not raw:
        return ""
    mac = str(raw).strip().upper().replace("-", ":")
    parts = mac.split(":")
    if len(parts) != 6:
        return ""
    if not all(
        len(p) == 2 and all(c in "0123456789ABCDEF" for c in p) for p in parts
    ):
        return ""
    return mac


def _client_hostname(request) -> str:
    raw = (
        request.GET.get("clienthostname")
        or request.POST.get("clienthostname")
        or request.GET.get("client_hostname")
        or request.POST.get("client_hostname")
        or request.GET.get("hostname")
        or request.POST.get("hostname")
        or ""
    )
    return str(raw).strip()[:64]


def _stash_client_identity(request) -> tuple[str, str]:
    """Remember openNDS client MAC + hostname for guest / device UI."""
    mac = _normalize_client_mac(
        request.GET.get("clientmac")
        or request.POST.get("clientmac")
        or request.GET.get("client_mac")
        or request.POST.get("client_mac")
        or request.GET.get("mac")
        or request.POST.get("mac")
        or ""
    )
    hostname = _client_hostname(request)

    if mac:
        request.session["guest_client_mac"] = mac
        request.session.modified = True
    if hostname:
        request.session["guest_client_hostname"] = hostname
        request.session.modified = True

    return mac, hostname


@method_decorator(csrf_exempt, name="dispatch")
class FASView(View):
    def get(self, request):
        _stash_client_identity(request)
        return FASService.handle(request)

    def post(self, request):
        _stash_client_identity(request)
        return FASService.handle(request)
