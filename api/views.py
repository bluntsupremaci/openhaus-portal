"""
Forward Authentication Service (FAS) View for openNDS.

This endpoint is called by openNDS captive portal to authorize network access.
"""

import logging

from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from devices.services.devices import DeviceService
from openhaus_portal.services import AuthorizationService
from quotas.services.quotas import QuotaService
from portal_sessions.services.sessions import SessionService
from memberships.services.memberships import MembershipService

from openhaus_portal.core.exceptions import DeviceNotFoundError

logger = logging.getLogger("api")


@method_decorator(csrf_exempt, name="dispatch")
class FASView(View):
    """
    Production-ready FAS endpoint for openNDS.

    Flow:
        1. Device lookup & validation
        2. Full authorization (account, device, membership)
        3. Quota validation
        4. Session creation
        5. Return allow/block response
    """

    def get(self, request):
        """Handle GET request from openNDS."""

        client_mac = request.GET.get("client_mac", "").strip().upper()
        client_ip = request.GET.get("client_ip")
        gateway = request.GET.get("gateway")
        user_agent = request.GET.get("user_agent", "")

        if not client_mac:
            logger.warning("FAS request missing client_mac")
            return JsonResponse(
                {"status": "error", "message": "MAC address required", "action": "block"},
                status=400,
            )

        logger.info(f"FAS request received for MAC={client_mac}")

        # ==============================================================
        # 1. Device Lookup / Registration
        # ==============================================================
        try:
            device = DeviceService.get_or_register_device(
                mac_address=client_mac,
                ip_address=client_ip,
                hostname=request.GET.get("client_hostname"),
                platform=user_agent,
            )
            DeviceService.update_last_seen(device)
        except DeviceNotFoundError:
            logger.warning(f"Unknown device: {client_mac}")
            return JsonResponse(
                {
                    "status": "error",
                    "message": "Device not registered",
                    "action": "block",
                },
                status=403,
            )

        user = device.user

        # ==============================================================
        # 2. Authorization (Account + Device + Membership)
        # ==============================================================
        try:
            AuthorizationService.can_access_network(user=user, device=device)
        except Exception as e:
            logger.warning(f"Authorization denied for {user.email}: {e}")
            return JsonResponse(
                {
                    "status": "error",
                    "message": str(e),
                    "action": "block",
                },
                status=403,
            )

        # ==============================================================
        # 3. Quota Validation
        # ==============================================================
        try:
            QuotaService.ensure_available(user=user, device=device, required_bytes=1024*1024)  # 1MB minimum check
        except Exception as e:
            logger.warning(f"Quota check failed for {user.email}: {e}")
            return JsonResponse(
                {
                    "status": "error",
                    "message": "Insufficient quota",
                    "action": "block",
                },
                status=403,
            )

        # ==============================================================
        # 4. Create / Update Session
        # ==============================================================
        try:
            session = SessionService.start_session(
                user=user,
                device=device,
                ip_address=client_ip,
                nas_ip=gateway,
            )
        except Exception as e:
            logger.error(f"Session creation failed for {user.email}: {e}")
            return JsonResponse(
                {
                    "status": "error",
                    "message": "Internal session error",
                    "action": "block",
                },
                status=500,
            )

        # ==============================================================
        # 5. Success Response
        # ==============================================================
        membership = MembershipService.get_active_membership(user)
        quota_remaining = QuotaService.get_available_quota(user)

        logger.info(f"Access granted to {user.email} via {client_mac}")

        return JsonResponse({
            "status": "success",
            "action": "allow",
            "username": user.email,
            "user_type": user.user_type,
            "membership": membership.plan.name if membership else "None",
            "quota_remaining": quota_remaining,
            "session_id": str(session.id),
        })