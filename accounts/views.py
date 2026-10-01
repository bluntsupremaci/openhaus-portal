"""
Accounts Views for OpenHaus.
Thin user-facing views (dashboard, device registration, profile, signup, etc.).
"""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from access_policy.services import AccessPolicyService
from accounts.models import CustomUser
from accounts.services.authentication import AuthService
from accounts.services.guest import GuestRewardService
from devices.services.devices import DeviceService
from memberships.services.memberships import MembershipService
from portal_sessions.services.sessions import SessionService
from quotas.services.quotas import QuotaService


def login_view(request: HttpRequest):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")

    if request.method == "POST":
        email = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        try:
            user = AuthService.authenticate_client(email=email, password=password)
            AuthService.login_user(request=request, user=user)
            if not user.is_email_verified:
                messages.warning(
                    request,
                    "Your email is not verified yet. You only have limited free access until you verify.",
                )
            return redirect("accounts:dashboard")
        except Exception as e:
            messages.error(request, str(e))

    return render(request, "registration/login.html")


def logout_view(request: HttpRequest):
    AuthService.logout_user(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect("accounts:login")


def signup_view(request: HttpRequest):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")

    context = {"email": ""}

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "").strip()
        password_confirm = request.POST.get("password_confirm", "").strip()
        user_type = (request.POST.get("user_type", "guest") or "guest").strip().lower()
        university_id = request.POST.get("university_id", "").strip() or None

        context["email"] = email

        if password != password_confirm:
            messages.error(request, "Passwords do not match.")
            return render(request, "registration/signup.html", context)

        if user_type in ("student", "staff"):
            if not AccessPolicyService.domain_allowed_for_student(email):
                messages.error(
                    request,
                    "Student and staff accounts must use your institution email "
                    "(@bazeuniversity.edu.ng).",
                )
                return render(request, "registration/signup.html", context)

        try:
            user = AuthService.register_user(
                email=email,
                password=password,
                user_type=user_type,
                university_id=university_id,
            )
            if getattr(settings, "AUTH_AUTO_VERIFY_EMAIL", False):
                user.is_email_verified = True
                user.save(update_fields=["is_email_verified"])

            AuthService.login_user(request=request, user=user)

            if not user.is_email_verified:
                try:
                    AuthService.send_verification_email(user, request=request)
                except Exception:
                    pass
                messages.success(
                    request,
                    "Account created. Check your email (or the server console in dev) "
                    "for a verification link. You have a short free access window until then.",
                )
            else:
                messages.success(
                    request,
                    "Account created and verified. Your benefits are active.",
                )
            return redirect("accounts:dashboard")
        except Exception as e:
            error_str = str(e).lower()
            if "email" in error_str and (
                "already exists" in error_str or "unique" in error_str
            ):
                messages.error(request, "An account with this email already exists.")
            else:
                messages.error(request, str(e))

    return render(request, "registration/signup.html", context)


@login_required
def dashboard(request: HttpRequest):
    user: CustomUser = request.user

    membership_summary = MembershipService.get_membership_summary(user)
    has_membership = bool(membership_summary.get("has_membership"))
    grant_seconds = AccessPolicyService.total_remaining_seconds(user)

    context = {
        "user": user,
        "role": AccessPolicyService.resolve_role(user),
        "grant_seconds_remaining": grant_seconds,
        "grant_minutes_remaining": max(0, grant_seconds // 60),
        "has_valid_grant": AccessPolicyService.has_valid_time_grant(user),
        "membership_summary": membership_summary,
        "has_active_membership": has_membership,
        "quota_status": QuotaService.get_quota_status(user) if has_membership else None,
        "devices": DeviceService.get_user_devices(user),
        "active_devices_count": DeviceService.get_active_devices(user).count(),
        "active_session": SessionService.get_active_session(user=user),
        "email_verified": user.is_email_verified,
    }
    return render(request, "accounts/dashboard.html", context)


@require_http_methods(["GET", "POST"])
@login_required
def register_device(request: HttpRequest):
    if request.method == "POST":
        mac_address = request.POST.get("mac_address", "").strip().upper()
        hostname = request.POST.get("hostname", "").strip()
        platform = request.POST.get("platform", "").strip()
        try:
            device = DeviceService.register_device(
                owner=request.user,
                mac_address=mac_address,
                hostname=hostname,
                platform=platform,
            )
            messages.success(
                request, f"Device '{device.mac_address}' registered successfully."
            )
            return redirect("accounts:dashboard")
        except Exception as e:
            messages.error(request, str(e))

    return render(request, "accounts/register_device.html")


@login_required
def profile(request: HttpRequest):
    user = request.user

    membership_summary = MembershipService.get_membership_summary(user)
    has_membership = bool(membership_summary.get("has_membership"))
    grant_seconds = AccessPolicyService.total_remaining_seconds(user)

    context = {
        "user": user,
        "role": AccessPolicyService.resolve_role(user),
        "grant_seconds_remaining": grant_seconds,
        "grant_minutes_remaining": max(0, grant_seconds // 60),
        "has_valid_grant": AccessPolicyService.has_valid_time_grant(user),
        "devices": DeviceService.get_user_devices(user),
        "membership_summary": membership_summary,
        "has_active_membership": has_membership,
        "quota_status": QuotaService.get_quota_status(user) if has_membership else None,
        "active_session": SessionService.get_active_session(user=user),
        "email_verified": user.is_email_verified,
    }
    return render(request, "accounts/profile.html", context)


@require_http_methods(["GET", "POST"])
def guest_access(request: HttpRequest):
    """
    Ad reward → time grant.
    MAC + optional hostname from openNDS/FAS query or session only.
    """

    def normalize_mac(raw) -> str:
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

    # Query first (portal redirect), then session
    mac = normalize_mac(
        request.GET.get("clientmac")
        or request.GET.get("client_mac")
        or request.GET.get("mac")
    )
    hostname_from_portal = (
        request.GET.get("clienthostname")
        or request.GET.get("client_hostname")
        or request.GET.get("hostname")
        or ""
    ).strip()[:64]

    if mac:
        request.session["guest_client_mac"] = mac
        request.session.modified = True
    else:
        mac = normalize_mac(request.session.get("guest_client_mac"))

    if hostname_from_portal:
        request.session["guest_client_hostname"] = hostname_from_portal
        request.session.modified = True

    session_hostname = (request.session.get("guest_client_hostname") or "").strip()

    # Prefer registered device name, else portal/session hostname
    device_name = ""
    if mac:
        try:
            device = DeviceService.get_device(mac)
            device_name = (
                getattr(device, "hostname", None)
                or getattr(device, "name", None)
                or ""
            )
            device_name = (device_name or "").strip()
        except Exception:
            device_name = ""

    if not device_name:
        device_name = session_hostname or hostname_from_portal or "Unknown device"

    policy = AccessPolicyService.settings()
    context = {
        "client_mac": mac,
        "mac_detected": bool(mac),
        "device_name": device_name,
        "ad_reward_enabled": getattr(policy, "ad_reward_enabled", True),
        "ad_reward_minutes": getattr(policy, "ad_reward_minutes", 20),
        "ad_daily_limit": getattr(policy, "ad_daily_limit", 3),
    }

    if request.method == "POST":
        if not mac:
            messages.error(
                request,
                "Device not detected. Join campus Wi‑Fi and open Guest access "
                "from the captive portal.",
            )
            return render(request, "accounts/guest_access.html", context)

        try:
            # Pass portal hostname so first registration is not always "guest-device"
            seconds = GuestRewardService.grant_ad_reward(
                mac,
                hostname=session_hostname or hostname_from_portal or None,
            )
            if seconds:
                minutes = max(1, int(seconds) // 60)
                messages.success(
                    request,
                    f"Success! About {minutes} minutes of free access for this device.",
                )
                # Refresh name after register
                try:
                    device = DeviceService.get_device(mac)
                    context["device_name"] = (
                        getattr(device, "hostname", None) or context["device_name"]
                    )
                except Exception:
                    pass
            else:
                messages.warning(
                    request,
                    "Daily ad limit reached or ad rewards are disabled. Try again later.",
                )
        except Exception as e:
            messages.error(request, f"Failed to process reward: {e}")

        return render(request, "accounts/guest_access.html", context)

    return render(request, "accounts/guest_access.html", context)

@login_required
def edit_profile(request: HttpRequest):
    user = request.user
    old_email = user.email

    if request.method == "POST":
        user.first_name = request.POST.get("first_name", user.first_name)
        user.last_name = request.POST.get("last_name", user.last_name)
        user.phone_number = request.POST.get("phone_number", user.phone_number) or None

        new_email = request.POST.get("email", "").strip().lower()
        if new_email and new_email != old_email:
            user.email = new_email
            user.is_email_verified = False
            user.email_verified_at = None

        try:
            user.full_clean()
            user.save()
            messages.success(request, "Profile updated successfully.")
            if new_email and new_email != old_email:
                messages.info(
                    request, "Your new email needs verification. Check your inbox."
                )
            return redirect("accounts:profile")
        except Exception as e:
            messages.error(request, str(e))

    return render(request, "accounts/edit_profile.html", {"user": user})


def verify_email(request: HttpRequest, uidb64: str, token: str):
    try:
        user = AuthService.verify_email_token(uidb64=uidb64, token=token)
        messages.success(
            request,
            "Email verified. Your account benefits (trial / visitor bonus) are now active.",
        )
        if not request.user.is_authenticated:
            AuthService.login_user(request=request, user=user)
        return redirect("accounts:dashboard")
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("accounts:login")


@login_required
def resend_verification(request: HttpRequest):
    if AuthService.resend_verification_email(request.user, request=request):
        messages.success(
            request,
            "Verification email sent. In development, check the runserver terminal for the link.",
        )
    else:
        messages.info(request, "Your email is already verified.")
    return redirect("accounts:profile")
