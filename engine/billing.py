"""
Billing and Premium Tier Management via Razorpay TEST Mode.
Stage 4: Test Mode verification, HMAC signature validation, replay protection,
and plan upgrade handlers.

Hard Security Principles:
- Strictly TEST MODE only. Rejects any key starting with 'rzp_live_'.
- Server-side cryptographic HMAC-SHA256 signature verification.
- Replay protection: Razorpay payment IDs are unique and cannot be reused.
- No client-side self-upgrade without valid verified signature.
- Clear TEST MODE UI messaging.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
from typing import Any
import uuid

import config
from engine.auth_client import _IN_MEMORY_PROFILES, get_supabase_client

logger = logging.getLogger(__name__)

# Premium Plan Pricing
PREMIUM_PRICE_INR = 499.00
PREMIUM_PRICE_PAISE = 49900  # 499.00 INR in paise

# In-memory ledger of redeemed payment IDs for replay protection
_PROCESSED_PAYMENTS: set[str] = set()


def is_test_mode_key(key_id: str | None) -> bool:
    """Validate that the Razorpay key is strictly a TEST MODE key."""
    if not key_id:
        return False
    if key_id.startswith("rzp_live_"):
        raise ValueError(
            "LIVE Razorpay key detected! The application is strictly restricted to TEST MODE (rzp_test_)."
        )
    return key_id.startswith("rzp_test_")


def get_razorpay_client() -> Any | None:
    """Initialize Razorpay client with test key validation."""
    key_id = config.RAZORPAY_KEY_ID
    key_secret = config.RAZORPAY_KEY_SECRET

    if not key_id or not key_secret:
        logger.warning("Razorpay keys not fully configured.")
        return None

    if not is_test_mode_key(key_id):
        raise ValueError("Live Razorpay keys prohibited. Platform is in TEST MODE only.")

    try:
        import razorpay
        return razorpay.Client(auth=(key_id, key_secret))
    except Exception as exc:
        logger.error("Failed to initialize Razorpay client: %s", exc)
        return None


def create_subscription_order(user_id: str, amount_paise: int = PREMIUM_PRICE_PAISE) -> dict[str, Any]:
    """Create a Razorpay order in TEST MODE for premium plan upgrade."""
    key_id = config.RAZORPAY_KEY_ID or "rzp_test_placeholder"

    # Ensure live key cannot be used
    is_test_mode_key(key_id)

    client = get_razorpay_client()
    if client is not None:
        try:
            order_data = {
                "amount": amount_paise,
                "currency": "INR",
                "receipt": f"rcpt_{user_id[:8]}_{uuid.uuid4().hex[:6]}",
                "notes": {
                    "user_id": user_id,
                    "plan": "premium",
                    "mode": "TEST_MODE",
                },
            }
            order = client.order.create(data=order_data)
            return {
                "success": True,
                "order_id": order["id"],
                "amount": order["amount"],
                "currency": order["currency"],
                "key_id": key_id,
                "is_test_mode": True,
            }
        except Exception as exc:
            logger.warning("Razorpay order creation error: %s. Using local test order.", exc)

    # Local fallback for hermetic testing or offline sandbox
    mock_order_id = f"order_test_{uuid.uuid4().hex[:14]}"
    return {
        "success": True,
        "order_id": mock_order_id,
        "amount": amount_paise,
        "currency": "INR",
        "key_id": key_id,
        "is_test_mode": True,
    }


def compute_test_signature(order_id: str, payment_id: str, secret: str | None = None) -> str:
    """Compute HMAC-SHA256 signature for Razorpay verification."""
    sec = secret or os.getenv("RAZORPAY_KEY_SECRET") or config.RAZORPAY_KEY_SECRET or "dummy_test_secret"
    msg = f"{order_id}|{payment_id}".encode("utf-8")
    return hmac.new(sec.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def verify_payment_signature(
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str,
    secret: str | None = None,
) -> bool:
    """Verify cryptographic HMAC SHA256 signature of a payment."""
    if not razorpay_order_id or not razorpay_payment_id or not razorpay_signature:
        return False

    sec = secret or os.getenv("RAZORPAY_KEY_SECRET") or config.RAZORPAY_KEY_SECRET or "dummy_test_secret"
    expected_sig = compute_test_signature(razorpay_order_id, razorpay_payment_id, secret=sec)
    return hmac.compare_digest(expected_sig, razorpay_signature)


def apply_verified_upgrade(
    user_id: str,
    razorpay_payment_id: str,
    razorpay_order_id: str,
    razorpay_signature: str,
    amount_paise: int = PREMIUM_PRICE_PAISE,
    access_token: str | None = None,
) -> dict[str, Any]:
    """
    Apply subscription upgrade upon cryptographic signature verification and replay check.
    """
    if not user_id:
        return {"success": False, "message": "User ID is required."}

    # 1. Anti-Replay Check
    if razorpay_payment_id in _PROCESSED_PAYMENTS:
        logger.warning("Replay attack blocked: Payment ID %s already redeemed.", razorpay_payment_id)
        return {
            "success": False,
            "message": "Payment ID already redeemed. Replay attack blocked.",
        }

    # 2. Cryptographic Signature Verification
    if not verify_payment_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature):
        logger.warning("Signature verification failed for payment %s", razorpay_payment_id)
        return {
            "success": False,
            "message": "Cryptographic signature verification failed.",
        }

    # 3. Amount Matching Check
    if amount_paise < PREMIUM_PRICE_PAISE:
        logger.warning("Insufficient payment amount: %s < %s", amount_paise, PREMIUM_PRICE_PAISE)
        return {
            "success": False,
            "message": f"Payment amount ({amount_paise} paise) does not match Premium price ({PREMIUM_PRICE_PAISE} paise).",
        }

    # 4. Record payment as redeemed (anti-replay)
    _PROCESSED_PAYMENTS.add(razorpay_payment_id)

    # 5. Upgrade user plan in profile store
    _IN_MEMORY_PROFILES[user_id] = "premium"

    # Attempt to persist in Supabase if reachable
    client = get_supabase_client(access_token)
    if client is not None:
        try:
            client.table("payments").insert({
                "razorpay_payment_id": razorpay_payment_id,
                "user_id": user_id,
                "amount": float(amount_paise) / 100.0,
                "status": "captured",
            }).execute()
        except Exception as exc:
            logger.debug("Could not write payment to Supabase payments table: %s", exc)

        try:
            client.table("profiles").update({"plan": "premium"}).eq("user_id", user_id).execute()
        except Exception as exc:
            logger.debug("Could not update profile plan in Supabase: %s", exc)

    return {
        "success": True,
        "plan": "premium",
        "payment_id": razorpay_payment_id,
        "amount_inr": amount_paise / 100.0,
        "message": "Account successfully upgraded to Premium! Unlimited daily runs unlocked.",
    }
