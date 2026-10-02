"""
Accounts Views for OpenHaus.
Thin user-facing views (dashboard, device registration, profile, signup, etc.).
"""

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_http_methods

from access_policy.services import AccessPolicyService
from accounts.models import CustomUser
from accounts.services.authentication import AuthService
from accounts.services.guest import GuestRewardService
from devices.services.devices import DeviceService
from memberships.services.memberships import MembershipService
from portal_sessions.services.sessions import SessionService
from quotas.services.quotas import QuotaService

ROLE_LABELS = {
    "student": "Student",
    "staff": "Staff",
    "guest": "Guest",
    "member": "Member",
}

VERIFICATION_LABELS = {
    "verified": "Verified",
    "unverified": "Not verified",
    "n/a": "",
}


def role_label_for(user) -> str:
    code = AccessPolicyService.resolve_role(user)
    return ROLE_LABELS.get(code, "Guest")


def verification_label_for(user) -> str:
    code = AccessPolicyService.resolve_verification_status(user)
    return VERIFICATION_LABELS.get(code, "")


def _role_context(user: CustomUser) -> dict:
    """Shared role + verification fields for dashboard/profile."""
    role_code = AccessPolicyService.resolve_role(user)
    ver_code = AccessPolicyService.resolve_verification_status(user)
    return {
        "role": role_code,
        "role_label": ROLE_LABELS.get(role_code, "Guest"),
        "verification_status": ver_code,
        "verification_label": VERIFICATION_LABELS.get(ver_code, ""),
        "email_verified": bool(getattr(user, "is_email_verified", False)),
    }


def _format_bytes(n) -> str:
    try:
        n = int(n or 0)
    except (TypeError, ValueError):
        return "—"
    if n < 1024:
        return f"{n} B"
    if n < 1024**2:
        return f"{n / 1024:.1f} KB"
    if n < 1024**3:
        return f"{n / (1024**2):.1f} MB"
    return f"{n / (1024**3):.2f} GB"


def _session_row(session) -> dict | None:
    """Normalize a portal session object for templates."""
    if not session:
        return None

    started = getattr(session, "started_at", None) or getattr(
        session, "created_at", None
    )
    ended = getattr(session, "ended_at", None)
    is_active = getattr(session, "is_active", None)
    if is_active is None:
        is_active = ended is None

    duration_display = "—"
    duration_seconds = getattr(session, "duration_seconds", None)
    if duration_seconds is not None and not is_active:
        try:
            secs = max(0, int(duration_seconds))
            h, rem = divmod(secs, 3600)
            m, s = divmod(rem, 60)
            if h:
                duration_display = f"{h}h {m}m"
            elif m:
                duration_display = f"{m}m {s}s"
            else:
                duration_display = f"{s}s"
        except (TypeError, ValueError):
            duration_display = "—"
    elif started:
        end_ref = ended or timezone.now()
        secs = max(0, int((end_ref - started).total_seconds()))
        h, rem = divmod(secs, 3600)
        m, s = divmod(rem, 60)
        if h:
            duration_display = f"{h}h {m}m"
        elif m:
            duration_display = f"{m}m {s}s"
        else:
            duration_display = f"{s}s"

    device = getattr(session, "device", None)
    mac = None
    hostname = None
    if device is not None:
        mac = getattr(device, "mac_address", None)
        hostname = getattr(device, "hostname", None) or getattr(device, "name", None)
    mac = mac or getattr(session, "mac_address", None) or getattr(
        session, "client_mac", None
    )
    hostname = hostname or getattr(session, "hostname", None)

    ip = (
        getattr(session, "ip_address", None)
        or getattr(session, "client_ip", None)
        or getattr(session, "ip", None)
    )

    bytes_up = getattr(session, "bytes_up", None)
    if bytes_up is None:
        bytes_up = getattr(session, "upload_bytes", None)
    bytes_down = getattr(session, "bytes_down", None)
    if bytes_down is None:
        bytes_down = getattr(session, "download_bytes", None)

    # WiFiSession stores total bytes_used (not separate up/down)
    bytes_used = getattr(session, "bytes_used", None)
    if bytes_up is None and bytes_down is None and bytes_used is not None:
        bytes_down = bytes_used  # show total as ↓ used

    auth_method = (
        getattr(session, "auth_method", None)
        or getattr(session, "access_type", None)
        or getattr(session, "grant_type", None)
        or ""
    )

    token = getattr(session, "token", None) or getattr(session, "session_token", None)

    return {
        "raw": session,
        "started_at": started,
        "ended_at": ended,
        "is_active": bool(is_active),
        "duration_display": duration_display,
        "mac_address": mac,
        "hostname": hostname or "",
        "ip_address": ip,
        "bytes_up": bytes_up,
        "bytes_down": bytes_down,
        "bytes_used": bytes_used,
        "bytes_up_display": _format_bytes(bytes_up) if bytes_up is not None else None,
        "bytes_down_display": (
            _format_bytes(bytes_down) if bytes_down is not None else None
        ),
        "bytes_used_display": (
            _format_bytes(bytes_used) if bytes_used is not None else None
        ),
        "auth_method": auth_method,
        "token": token,
    }


def _access_page_context(user: CustomUser) -> dict:
    membership_summary = MembershipService.get_membership_summary(user)
    has_membership = bool(membership_summary.get("has_membership"))
    grant_seconds = AccessPolicyService.total_remaining_seconds(user)

    active_raw = SessionService.get_active_session(user=user)
    try:
        recent_raw = list(SessionService.get_user_sessions(user=user, limit=20))
    except Exception:
        recent_raw = [active_raw] if active_raw is not None else []

    if has_membership:
        default_auth = "membership"
    elif AccessPolicyService.has_valid_time_grant(user):
        default_auth = "grant"
    else:
        default_auth = "none"

    active_session = _session_row(active_raw)
    if active_session and not active_session["auth_method"]:
        active_session["auth_method"] = default_auth

    recent_sessions = []
    for s in recent_raw:
        row = _session_row(s)
        if row:
            if not row["auth_method"]:
                row["auth_method"] = default_auth if row["is_active"] else ""
            recent_sessions.append(row)

    return {
        "user": user,
        **_role_context(user),
        "grant_seconds_remaining": grant_seconds,
        "grant_minutes_remaining": max(0, grant_seconds // 60),
        "has_valid_grant": AccessPolicyService.has_valid_time_grant(user),
        "membership_summary": membership_summary,
        "has_active_membership": has_membership,
        "devices": DeviceService.get_user_devices(user),
        "active_devices_count": DeviceService.get_active_devices(user).count(),
        "active_session": active_session,
        "active_session_raw": active_raw,
        "recent_sessions": recent_sessions,
    }

@login_required
@require_GET
def access_details(request: HttpRequest):
    return render(
        request,
        "accounts/access_details.html",
        _access_page_context(request.user),
    )


@login_required
@require_GET
def session_details(request: HttpRequest):
    return render(
        request,
        "accounts/session_details.html",
        _access_page_context(request.user),
    )


def login_view(request: HttpRequest):
    def safe_next(raw: str | None) -> str | None:
        if not raw:
            return None
        if url_has_allowed_host_and_scheme(
            raw,
            allowed_hosts={request.get_host()},
            require_https=request.is_secure(),
        ):
            return raw
        return None

    if request.user.is_authenticated:
        nxt = safe_next(request.GET.get("next") or request.POST.get("next"))
        return redirect(nxt or "accounts:dashboard")

    if request.method == "POST":
        email = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()
        try:
            user = AuthService.authenticate_client(email=email, password=password)
            AuthService.login_user(request=request, user=user)

            ut = (getattr(user, "user_type", None) or "guest").strip().lower()
            if ut in ("student", "staff") and not user.is_email_verified:
                messages.warning(
                    request,
                    "Your email is not verified yet. You only have limited free access until you verify.",
                )

            nxt = safe_next(request.POST.get("next") or request.GET.get("next"))
            return redirect(nxt or "accounts:dashboard")
        except Exception as e:
            messages.error(request, str(e))

    return render(
        request,
        "registration/login.html",
        {"next": request.GET.get("next", "")},
    )

def _session_row_json(row: dict | None) -> dict | None:
    """JSON-safe copy of a _session_row dict."""
    if not row:
        return None

    def _dt(v):
        if v is None:
            return None
        try:
            return v.isoformat()
        except Exception:
            return str(v)

    return {
        "is_active": row.get("is_active"),
        "started_at": _dt(row.get("started_at")),
        "ended_at": _dt(row.get("ended_at")),
        "duration_display": row.get("duration_display"),
        "mac_address": row.get("mac_address"),
        "hostname": row.get("hostname") or "",
        "ip_address": row.get("ip_address"),
        "bytes_used_display": row.get("bytes_used_display"),
        "bytes_up_display": row.get("bytes_up_display"),
        "bytes_down_display": row.get("bytes_down_display"),
        "auth_method": row.get("auth_method") or "",
        "token": row.get("token"),
    }

@login_required
@require_GET
def session_status_api(request: HttpRequest) -> JsonResponse:
    """Polled by the session page every ~15s."""
    ctx = _access_page_context(request.user)
    return JsonResponse(
        {
            "active_session": _session_row_json(ctx.get("active_session")),
            "recent_sessions": [
                _session_row_json(s) for s in (ctx.get("recent_sessions") or []) if s
            ],
            "server_time": timezone.now().isoformat(),
        }
    )

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

            if user_type in ("student", "staff") and not user.is_email_verified:
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
                    "Account created. Your access is ready.",
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
        **_role_context(user),
        "grant_seconds_remaining": grant_seconds,
        "grant_minutes_remaining": max(0, grant_seconds // 60),
        "has_valid_grant": AccessPolicyService.has_valid_time_grant(user),
        "membership_summary": membership_summary,
        "has_active_membership": has_membership,
        "quota_status": QuotaService.get_quota_status(user) if has_membership else None,
        "devices": DeviceService.get_user_devices(user),
        "active_devices_count": DeviceService.get_active_devices(user).count(),
        "active_session": SessionService.get_active_session(user=user),
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
        **_role_context(user),
        "grant_seconds_remaining": grant_seconds,
        "grant_minutes_remaining": max(0, grant_seconds // 60),
        "has_valid_grant": AccessPolicyService.has_valid_time_grant(user),
        "devices": DeviceService.get_user_devices(user),
        "membership_summary": membership_summary,
        "has_active_membership": has_membership,
        "quota_status": QuotaService.get_quota_status(user) if has_membership else None,
        "active_session": SessionService.get_active_session(user=user),
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
