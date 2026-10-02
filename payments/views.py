from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods

from memberships.models import MembershipPlan
from memberships.services.memberships import MembershipService
from payments.services import PaymentService, PaymentServiceError


def _shop_plans():
    """Paid, active plans only (exclude trial / free grants)."""
    return (
        MembershipPlan.objects.filter(is_active=True, price__gt=0)
        .order_by("price", "duration_days")
    )


@login_required
@require_GET
def plan_list(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "payments/plan_list.html",
        {"plans": _shop_plans()},
    )


@login_required
@require_GET
def membership_hub(request: HttpRequest) -> HttpResponse:
    user = request.user
    summary = MembershipService.get_membership_summary(user)
    active = MembershipService.get_active_membership(user)
    is_trial = bool(
        active
        and active.plan
        and (active.plan.price is None or active.plan.price <= 0)
    )
    return render(
        request,
        "payments/membership_hub.html",
        {
            "membership_summary": summary,
            "active_membership": active,
            "plans": _shop_plans(),
            "has_active_membership": bool(summary.get("has_membership")),
            "is_trial": is_trial,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def checkout(request: HttpRequest, plan_id) -> HttpResponse:
    plan = get_object_or_404(MembershipPlan, pk=plan_id, is_active=True)

    if plan.price is None or plan.price <= 0:
        messages.error(request, "This plan cannot be purchased.")
        return redirect("payments:membership_hub")

    if request.method == "GET":
        return render(request, "payments/checkout.html", {"plan": plan})

    callback_url = request.build_absolute_uri(reverse("payments:callback"))
    try:
        _payment, auth_url = PaymentService.start_checkout(
            user=request.user,
            plan=plan,
            callback_url=callback_url,
        )
    except PaymentServiceError as e:
        messages.error(request, str(e))
        return redirect("payments:membership_hub")

    return redirect(auth_url)


@login_required
@require_GET
def callback(request: HttpRequest) -> HttpResponse:
    reference = (
        request.GET.get("reference") or request.GET.get("trxref") or ""
    ).strip()
    if not reference:
        messages.error(request, "Missing payment reference.")
        return redirect("payments:membership_hub")

    try:
        payment = PaymentService.fulfill_by_reference(reference)
    except PaymentServiceError as e:
        messages.error(request, str(e))
        return redirect("payments:membership_hub")

    messages.success(
        request,
        f"Payment successful. Your {payment.plan.name} membership is active.",
    )
    return redirect("accounts:dashboard")
