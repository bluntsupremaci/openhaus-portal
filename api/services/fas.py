"""
Forward Authentication Service (FAS) for openNDS.

Parses openNDS query parameters, runs authorization, and builds
HTTP responses (redirect for production path, JSON for debugging).
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from django.conf import settings
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect, JsonResponse

from accounts.services.authorization import AuthorizationService
from openhaus_portal.core.exceptions import OpenHausError


@dataclass(frozen=True)
class FASRequestParams:
    client_mac: str
    client_ip: str | None
    gateway: str | None
    hostname: str | None
    user_agent: str | None
    token: str | None
    authaction: str | None
    redir: str | None
    raw: dict[str, str]


class FASService:
    """openNDS-facing FAS orchestration."""

    @staticmethod
    def parse_request(request: HttpRequest) -> FASRequestParams:
        g = request.GET

        def first(*keys: str) -> str | None:
            for key in keys:
                value = g.get(key)
                if value is not None and str(value).strip() != "":
                    return str(value).strip()
            return None

        mac = first("clientmac", "client_mac", "mac") or ""
        return FASRequestParams(
            client_mac=mac.upper(),
            client_ip=first("clientip", "client_ip", "ip"),
            gateway=first("gatewayname", "gateway", "gatewayaddress", "nas_ip"),
            hostname=first("client_hostname", "hostname"),
            user_agent=first("user_agent", "useragent") or request.META.get("HTTP_USER_AGENT", ""),
            token=first("tok", "token", "hid"),
            authaction=first("authaction", "auth_action"),
            redir=first("redir", "originurl", "redirect"),
            raw={k: g.get(k, "") for k in g.keys()},
        )

    @staticmethod
    def handle(request: HttpRequest) -> HttpResponse:
        params = FASService.parse_request(request)
        want_json = request.GET.get("format") == "json" or request.headers.get(
            "Accept", ""
        ).startswith("application/json")

        if not params.client_mac:
            return FASService._deny(
                reason="MAC address required",
                status=400,
                want_json=want_json,
                params=params,
            )

        try:
            result = AuthorizationService.authorize_network_access(
                mac_address=params.client_mac,
                ip_address=params.client_ip,
                nas_ip=params.gateway,
                hostname=params.hostname,
                platform=params.user_agent,
            )
        except OpenHausError as exc:
            return FASService._deny(
                reason=str(exc),
                status=403,
                want_json=want_json,
                params=params,
            )
        except Exception:
            return FASService._deny(
                reason="Internal authorization error",
                status=500,
                want_json=want_json,
                params=params,
            )

        if want_json or not params.authaction:
            # Debug / lab path when openNDS authaction is not present.
            payload = {
                "status": result["status"],
                "action": result["action"],
                "username": result["username"],
                "user_type": result["user_type"],
                "membership": result["membership"],
                "quota_remaining": result["quota_remaining"],
                "session_id": result["session_id"],
            }
            if not params.authaction:
                payload["warning"] = (
                    "No authaction in request; returned JSON only. "
                    "Configure openNDS FAS so the browser is redirected with authaction+tok."
                )
            return JsonResponse(payload)

        return FASService._allow_redirect(params)

    @staticmethod
    def _allow_redirect(params: FASRequestParams) -> HttpResponse:
        """
        Level-0 style completion: send the client browser back to openNDS
        authaction with the original token so openNDS can grant access.
        """
        authaction = params.authaction
        assert authaction is not None

        parsed = urlparse(authaction)
        query = parse_qs(parsed.query)

        if params.token:
            # openNDS level 0 uses tok=
            query["tok"] = [params.token]
        if params.redir:
            query["redir"] = [params.redir]

        # Flatten parse_qs lists
        flat = {k: v[0] if isinstance(v, list) and v else v for k, v in query.items()}
        new_query = urlencode(flat)
        target = urlunparse(
            (
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                new_query,
                parsed.fragment,
            )
        )
        return HttpResponseRedirect(target)

    @staticmethod
    def _deny(
        *,
        reason: str,
        status: int,
        want_json: bool,
        params: FASRequestParams,
    ) -> HttpResponse:
        if want_json:
            return JsonResponse(
                {"status": "error", "message": reason, "action": "block"},
                status=status,
            )

        portal_url = getattr(settings, "FAS_PORTAL_LOGIN_URL", "/accounts/login/")
        guest_url = getattr(settings, "FAS_GUEST_URL", "/accounts/guest/")
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>OpenHaus — Access Denied</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 28rem; margin: 3rem auto; padding: 0 1rem; }}
    a {{ color: #0b57d0; }}
  </style>
</head>
<body>
  <h1>Network access denied</h1>
  <p>{reason}</p>
  <p><a href="{portal_url}">Sign in</a> · <a href="{guest_url}">Guest access</a></p>
</body>
</html>"""
        return HttpResponse(html, status=status, content_type="text/html; charset=utf-8")
