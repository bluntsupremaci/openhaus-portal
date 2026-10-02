"""Thin Paystack API client (initialize + verify)."""

from __future__ import annotations

from typing import Any

import requests
from django.conf import settings


class PaystackError(Exception):
    """Raised when Paystack API returns an error or is misconfigured."""


def _secret() -> str:
    key = (getattr(settings, "PAYSTACK_SECRET_KEY", None) or "").strip()
    if not key:
        raise PaystackError("PAYSTACK_SECRET_KEY is not set in the environment.")
    return key


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_secret()}",
        "Content-Type": "application/json",
    }


def initialize_transaction(
    *,
    email: str,
    amount_kobo: int,
    reference: str,
    callback_url: str,
    currency: str = "NGN",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Start a payment. Returns Paystack data:
    authorization_url, access_code, reference
    """
    if amount_kobo < 100:
        raise PaystackError("Amount too small (minimum 100 kobo / 1 NGN).")

    payload = {
        "email": email,
        "amount": int(amount_kobo),
        "reference": reference,
        "callback_url": callback_url,
        "currency": currency or "NGN",
        "metadata": metadata or {},
    }

    response = requests.post(
        "https://api.paystack.co/transaction/initialize",
        headers=_headers(),
        json=payload,
        timeout=30,
    )
    try:
        body = response.json()
    except ValueError as exc:
        raise PaystackError(f"Invalid Paystack response: {response.text[:200]}") from exc

    if not body.get("status"):
        raise PaystackError(body.get("message") or "Initialize transaction failed")

    return body["data"]


def verify_transaction(reference: str) -> dict[str, Any]:
    """
    Confirm payment status with Paystack.
    Returns data dict (status, amount, reference, metadata, ...).
    """
    response = requests.get(
        f"https://api.paystack.co/transaction/verify/{reference}",
        headers=_headers(),
        timeout=30,
    )
    try:
        body = response.json()
    except ValueError as exp:
        raise PaystackError(f"Invalid Paystack response: {response.text[:200]}") from exp

    if not body.get("status"):
        raise PaystackError(body.get("message") or "Verify transaction failed")

    return body["data"]
