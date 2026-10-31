"""
Unit and Integration Tests for Stage 4: Razorpay Test Mode & Premium Upgrades.
"""

from __future__ import annotations

import pytest

import config
from engine.auth_client import _IN_MEMORY_PROFILES, check_run_limit, record_run
from engine.billing import (
    _PROCESSED_PAYMENTS,
    PREMIUM_PRICE_PAISE,
    apply_verified_upgrade,
    compute_test_signature,
    create_subscription_order,
    is_test_mode_key,
    verify_payment_signature,
)


@pytest.fixture(autouse=True)
def reset_billing_fixtures():
    """Clear processed payment ledger before each test."""
    _PROCESSED_PAYMENTS.clear()
    _IN_MEMORY_PROFILES.clear()
    yield
    _PROCESSED_PAYMENTS.clear()
    _IN_MEMORY_PROFILES.clear()


class TestLiveKeyProhibition:
    """Security Gate: Ensure live keys are strictly prohibited."""

    def test_live_key_raises_value_error(self):
        with pytest.raises(ValueError) as exc_info:
            is_test_mode_key("rzp_live_1234567890abcdef")
        assert "LIVE Razorpay key detected" in str(exc_info.value)

    def test_test_mode_key_accepted(self):
        assert is_test_mode_key("rzp_test_1234567890abcdef") is True

    def test_empty_or_none_key_rejected(self):
        assert is_test_mode_key(None) is False
        assert is_test_mode_key("") is False


class TestSignatureVerification:
    """Cryptographic signature integrity checks."""

    def test_valid_signature_passes(self):
        order_id = "order_test_123"
        payment_id = "pay_test_456"
        secret = "test_secret_key_xyz"

        sig = compute_test_signature(order_id, payment_id, secret=secret)
        assert verify_payment_signature(order_id, payment_id, sig, secret=secret) is True

    def test_tampered_signature_fails(self):
        order_id = "order_test_123"
        payment_id = "pay_test_456"
        secret = "test_secret_key_xyz"

        tampered_sig = "a" * 64
        assert verify_payment_signature(order_id, payment_id, tampered_sig, secret=secret) is False

    def test_mismatched_order_id_fails(self):
        order_id = "order_test_123"
        payment_id = "pay_test_456"
        secret = "test_secret_key_xyz"

        sig = compute_test_signature(order_id, payment_id, secret=secret)
        assert verify_payment_signature("order_wrong_999", payment_id, sig, secret=secret) is False


class TestPremiumUpgradeWorkflow:
    """Plan upgrade, replay protection, and run limit unlocking."""

    def test_successful_verified_upgrade_unlocks_limits(self):
        user_id = "user_upgrade_test_001"
        _IN_MEMORY_PROFILES[user_id] = "free"

        # Initially 3 runs used -> blocked
        for i in range(3):
            record_run(user_id, f"Thesis {i}")
        assert check_run_limit(user_id, plan="free")["allowed"] is False

        # Create order and compute valid test signature
        order_res = create_subscription_order(user_id)
        order_id = order_res["order_id"]
        payment_id = "pay_test_success_001"
        secret = config.RAZORPAY_KEY_SECRET or "dummy_secret"

        sig = compute_test_signature(order_id, payment_id, secret=secret)

        # Apply upgrade
        upgrade_res = apply_verified_upgrade(
            user_id=user_id,
            razorpay_payment_id=payment_id,
            razorpay_order_id=order_id,
            razorpay_signature=sig,
            amount_paise=PREMIUM_PRICE_PAISE,
        )

        assert upgrade_res["success"] is True
        assert upgrade_res["plan"] == "premium"
        assert _IN_MEMORY_PROFILES[user_id] == "premium"

        # Now runs are unlocked (unlimited)
        limits = check_run_limit(user_id, plan="premium")
        assert limits["allowed"] is True
        assert limits["remaining"] == "unlimited"

    def test_replay_attack_rejected(self):
        user_id = "user_replay_test"
        order_id = "order_test_replay"
        payment_id = "pay_test_replay_001"
        secret = config.RAZORPAY_KEY_SECRET or "dummy_secret"
        sig = compute_test_signature(order_id, payment_id, secret=secret)

        # First application succeeds
        res1 = apply_verified_upgrade(user_id, payment_id, order_id, sig)
        assert res1["success"] is True

        # Second application with SAME payment_id must fail
        res2 = apply_verified_upgrade(user_id, payment_id, order_id, sig)
        assert res2["success"] is False
        assert "already redeemed" in res2["message"]

    def test_amount_mismatch_rejected(self):
        user_id = "user_amount_test"
        order_id = "order_test_amt"
        payment_id = "pay_test_amt_001"
        secret = config.RAZORPAY_KEY_SECRET or "dummy_secret"
        sig = compute_test_signature(order_id, payment_id, secret=secret)

        # User attempts to pass 100 paise (INR 1.00) instead of 49900 paise
        res = apply_verified_upgrade(
            user_id,
            payment_id,
            order_id,
            sig,
            amount_paise=100,
        )
        assert res["success"] is False
        assert "does not match" in res["message"]
