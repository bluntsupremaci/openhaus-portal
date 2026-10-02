"""Create payments and fulfill membership after Paystack success."""

from __future__ import annotations

import uuid
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from accounts.models import CustomUser
from memberships.models import MembershipPlan, MembershipStatus
from memberships.services.memberships import MembershipService
from openhaus_portal.core import logger
from payments.models import Payment, PaymentStatus
from payments.paystack import PaystackError, initialize_transaction, verify_transaction


class PaymentServiceError(Exception):
    pass


def _make_reference(user: CustomUser) -> str:
    uid = str(getattr(user, "id", "x")).replace("-", "")[:8]
    return f"oh_{uid}_{uuid.uuid4().hex[:12]}"


class PaymentService:
    @staticmethod
    def start_checkout(
        *,
        user: CustomUser,
        plan: MembershipPlan,
        callback_url: str,
    ) -> tuple[Payment, str]:
        """
        Create a pending Payment and initialize Paystack.
        Returns (payment, authorization_url).
        """
        if not plan.is_active:
            raise PaymentServiceError("This plan is not available.")
        if plan.price is None or plan.price <= 0:
            raise PaymentServiceError("This plan has no payable price.")

        reference = _make_reference(user)
        payment = Payment.objects.create(
            user=user,
            plan=plan,
            amount=plan.price,
            currency=(plan.currency or "NGN").upper(),
            reference=reference,
            status=PaymentStatus.PENDING,
        )

        try:
            data = initialize_transaction(
                email=user.email,
                amount_kobo=payment.amount_kobo,
                reference=reference,
                callback_url=callback_url,
                currency=payment.currency,
                metadata={
                    "payment_id": str(payment.id),
                    "plan_id": str(plan.id),
                    "user_id": str(user.id),
                },
            )
        except PaystackError as e:
            payment.status = PaymentStatus.FAILED
            payment.save(update_fields=["status", "updated_at"])
            raise PaymentServiceError(str(e)) from e

        payment.paystack_access_code = data.get("access_code") or ""
        payment.save(update_fields=["paystack_access_code", "updated_at"])

        url = data.get("authorization_url")
        if not url:
            raise PaymentServiceError("Paystack did not return a payment URL.")

        logger.log_event(
            "PAYMENT_INITIALIZED",
            "Checkout started",
            user=user.email,
            reference=reference,
            plan=plan.slug if hasattr(plan, "slug") else plan.name,
        )
        return payment, url

    @staticmethod
    @transaction.atomic
    def fulfill_by_reference(reference: str) -> Payment:
        """
        Verify with Paystack and activate/renew/replace membership.
        Idempotent: safe to call twice for the same reference.
        """
        try:
            payment = (
                Payment.objects.select_for_update()
                .select_related("user", "plan", "membership")
                .get(reference=reference)
            )
        except Payment.DoesNotExist as e:
            raise PaymentServiceError("Unknown payment reference.") from e

        if payment.status == PaymentStatus.SUCCESS:
            return payment

        try:
            data = verify_transaction(reference)
        except PaystackError as e:
            raise PaymentServiceError(str(e)) from e

        payment.raw_verify_response = data

        if (data.get("status") or "").lower() != "success":
            payment.status = PaymentStatus.FAILED
            payment.save(
                update_fields=["status", "raw_verify_response", "updated_at"]
            )
            raise PaymentServiceError("Payment was not successful.")

        paid_kobo = int(data.get("amount") or 0)
        if paid_kobo != payment.amount_kobo:
            payment.status = PaymentStatus.FAILED
            payment.save(
                update_fields=["status", "raw_verify_response", "updated_at"]
            )
            raise PaymentServiceError("Paid amount does not match plan price.")

        user = payment.user
        plan = payment.plan
        membership = PaymentService._apply_purchased_plan(user=user, plan=plan)

        payment.membership = membership
        payment.status = PaymentStatus.SUCCESS
        payment.paid_at = timezone.now()
        payment.save(
            update_fields=[
                "membership",
                "status",
                "paid_at",
                "raw_verify_response",
                "updated_at",
            ]
        )

        logger.log_event(
            "PAYMENT_SUCCESS",
            "Membership fulfilled",
            user=user.email,
            reference=reference,
            plan=getattr(plan, "slug", None) or plan.name,
            membership_id=str(membership.id),
        )
        return payment

    @staticmethod
    def _apply_purchased_plan(*, user, plan):
        """
        No active  → create + activate purchased plan
        Same plan  → extend end_date by plan.duration_days
        Other plan → end current (valid end_date), activate new from today
        """

        active = MembershipService.get_active_membership(user)
        now = timezone.now()

        if active is None:
            m = MembershipService.create_membership(user=user, plan=plan)
            return MembershipService.activate_membership(m)

        # Same plan → extend
        if active.plan_id == plan.id:
            days = int(plan.duration_days or 0)
            base = active.end_date or now
            if base < now:
                base = now
            active.end_date = base + timedelta(days=days)
            fields = ["end_date"]
            if hasattr(active, "updated_at"):
                fields.append("updated_at")
            active.save(update_fields=fields)
            logger.log_event(
                "MEMBERSHIP_EXTENDED",
                "Same plan renewed",
                user=user.email,
                plan=plan.name,
                days=days,
            )
            return active

        # Different plan → end current safely, then activate new
        start = active.start_date or now
        end = now
        if end <= start:
            end = start + timedelta(seconds=1)

        active.status = MembershipStatus.EXPIRED
        active.end_date = end
        fields = ["status", "end_date"]
        if hasattr(active, "updated_at"):
            fields.append("updated_at")
        active.save(update_fields=fields)

        m = MembershipService.create_membership(user=user, plan=plan)
        m = MembershipService.activate_membership(m)
        logger.log_event(
            "MEMBERSHIP_REPLACED",
            "Switched plan after purchase",
            user=user.email,
            old_plan=str(getattr(active.plan, "name", active.plan_id)),
            new_plan=plan.name,
        )
        return m
