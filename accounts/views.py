"""
Accounts Views for OpenHaus.
User-facing views (dashboard, device registration, profile, signup, etc.).
"""

from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.shortcuts import render, redirect
from django.contrib import messages
from django.http import HttpRequest
from django.views.decorators.http import require_http_methods

from accounts.models import CustomUser
from accounts.services.authentication import AuthService

# Other services
from memberships.services.memberships import MembershipService
from devices.services.devices import DeviceService
from quotas.services.quotas import QuotaService
from portal_sessions.services.sessions import SessionService
from django.conf import settings
from accounts.services.guest import GuestRewardService


# ====================== AUTH VIEWS ======================
def login_view(request: HttpRequest):
    """Custom login view using email."""
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")

    if request.method == "POST":
        email = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()

        try:
            user = AuthService.authenticate_client(email=email, password=password)
            AuthService.login_user(request=request, user=user)
            return redirect("accounts:dashboard")
        except Exception as e:
            messages.error(request, str(e))

    return render(request, "registration/login.html")


def logout_view(request):
    """Logout user."""
    logout(request)
    messages.success(request, "You have been logged out successfully.")
    return redirect("accounts:login")


def signup_view(request: HttpRequest):
    """User signup view with proper flow."""
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")

    context = {"email": ""}

    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        password = request.POST.get("password", "").strip()
        password_confirm = request.POST.get("password_confirm", "").strip()
        user_type = request.POST.get("user_type", "guest")
        university_id = request.POST.get("university_id", "").strip()

        context["email"] = email

        if password != password_confirm:
            messages.error(request, "Passwords do not match.")
            return render(request, "registration/signup.html", context)

        try:
            User = get_user_model()
            user = User.objects.create_user(
                email=email,
                password=password,
                user_type=user_type,
                university_id=university_id if user_type in ["student", "staff"] else None,
            )

            # Grant temporary access immediately
            AuthService.grant_temporary_access(user)

            # Auto-login the user after signup
            login(request, user)

            messages.success(request, "Account created successfully! A verification email has been sent to your inbox.")
            return redirect("accounts:dashboard")

        except Exception as e:
            error_str = str(e).lower()
            if "email" in error_str and ("already exists" in error_str or "unique" in error_str):
                messages.error(request, "An account with this email already exists.")
            else:
                messages.error(request, str(e))

    return render(request, "registration/signup.html", context)


# ====================== MAIN VIEWS ======================
@login_required
def dashboard(request: HttpRequest):
    """Main user dashboard."""
    user: CustomUser = request.user
    context = {"user": user}

    try:
        context["membership_summary"] = MembershipService.get_membership_summary(user)
        context["has_active_membership"] = True
    except Exception:
        context["membership_summary"] = None
        context["has_active_membership"] = False

    try:
        context["quota_status"] = QuotaService.get_quota_status(user)
    except Exception:
        context["quota_status"] = None

    context["devices"] = DeviceService.get_user_devices(user)
    context["active_devices_count"] = DeviceService.get_active_devices(user).count()

    context["active_session"] = SessionService.get_active_session(user=user)

    return render(request, "accounts/dashboard.html", context)


@require_http_methods(["GET", "POST"])
@login_required
def register_device(request: HttpRequest):
    """Register a new device for the current user."""
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
            messages.success(request, f"Device '{device.mac_address}' registered successfully.")
            return redirect("accounts:dashboard")
        except Exception as e:
            messages.error(request, str(e))

    return render(request, "accounts/register_device.html")


@login_required
def profile(request: HttpRequest):
    """User profile view with useful information."""
    user = request.user
    context = {
        "user": user,
        "devices": DeviceService.get_user_devices(user),
        "membership_summary": MembershipService.get_membership_summary(user),
        "quota_status": QuotaService.get_quota_status(user),
        "active_session": SessionService.get_active_session(user=user),
    }
    return render(request, "accounts/profile.html", context)


def guest_access(request: HttpRequest):
    """Simple guest access - watch ad for temporary Wi-Fi."""
    context = {
        "title": "Free Guest Access",
    }


    if request.method == "POST":
        # In real implementation, verify ad was watched (via API or token)
        messages.success(request, "Thank you for watching! You've received 30 minutes of free access.")
        # TODO: Create temporary session / quota
        return redirect("accounts:login")

    return render(request, "accounts/guest_access.html", context)

@require_http_methods(["GET", "POST"])
def guest_access(request: HttpRequest):
    """Guest access via watching an ad for temporary quota."""
    if request.method == "POST":
        client_mac = request.POST.get("client_mac") or request.META.get("REMOTE_ADDR", "unknown")

        try:
            reward = GuestRewardService.grant_ad_reward(client_mac)
            if reward:
                messages.success(
                    request, 
                    f"🎉 Success! You received {settings.GUEST_AD_REWARD_MB}MB of free data."
                )
            else:
                messages.warning(request, "Daily limit reached or reward failed. Try again later.")
        except Exception as e:
            messages.error(request, f"Failed to process reward: {str(e)}")

        return redirect("accounts:guest_access")

    return render(request, "accounts/guest_access.html")

@login_required
def edit_profile(request: HttpRequest):
    """Edit profile (except university_id)."""
    user = request.user
    old_email = user.email

    if request.method == "POST":
        user.first_name = request.POST.get("first_name", user.first_name)
        user.last_name = request.POST.get("last_name", user.last_name)
        user.phone_number = request.POST.get("phone_number", user.phone_number)

        new_email = request.POST.get("email", "").strip().lower()

        if new_email and new_email != old_email:
            user.email = new_email
            user.is_email_verified = False
            user.email_verified_at = None

        try:
            user.full_clean()
            user.save()
            messages.success(request, "Profile updated successfully.")

            if new_email != old_email:
                messages.info(request, "Your new email needs verification. Check your inbox.")

            return redirect("accounts:profile")
        except Exception as e:
            messages.error(request, str(e))

    context = {"user": user}
    return render(request, "accounts/edit_profile.html", context)

@login_required
def resend_verification(request: HttpRequest):
    """Resend verification email."""
    if AuthService.resend_verification_email(request.user):
        messages.success(request, "Verification email has been resent. Please check your inbox.")
    else:
        messages.info(request, "Your email is already verified.")

    return redirect("accounts:profile")