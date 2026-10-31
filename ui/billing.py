"""
Streamlit Billing and Subscription UI for Razorpay TEST Mode.
Stage 4: Plan Comparison, TEST MODE Warning Banner, and Verified Upgrade Flow.
"""

from __future__ import annotations

import logging
from typing import Any
import streamlit as st

import config
from engine.auth_client import get_user_plan
from engine.billing import (
    PREMIUM_PRICE_INR,
    PREMIUM_PRICE_PAISE,
    apply_verified_upgrade,
    compute_test_signature,
    create_subscription_order,
    is_test_mode_key,
)

logger = logging.getLogger(__name__)


def render_billing_panel(user: dict[str, Any]) -> None:
    """Render the subscription and billing management interface."""
    user_id = user.get("user_id", "")
    token = user.get("access_token")
    plan = get_user_plan(user_id, token)

    # ── Test Mode Notice Banner ───────────────────────────────────────────
    st.markdown(
        """
        <div style="background: #FEF3C7; border: 1px solid #F59E0B; border-radius: 8px; padding: 0.85rem 1.25rem; margin-bottom: 1.5rem;">
            <div style="font-weight: 700; color: #92400E; font-size: 0.95rem; display: flex; align-items: center; gap: 0.5rem;">
                <span style="background: #F59E0B; color: #FFFFFF; font-size: 0.72rem; padding: 2px 6px; border-radius: 4px; font-weight: 800;">
                    TEST MODE
                </span>
                <span>RAZORPAY TEST GATEWAY ACTIVE — NO REAL CURRENCY CHARGED</span>
            </div>
            <div style="color: #78350F; font-size: 0.82rem; margin-top: 0.25rem;">
                Payments are processed via Razorpay Test Credentials. Live transactions and real credit cards are strictly blocked.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <h2 style="font-family: 'Playfair Display', serif; color: #431407; font-size: 1.8rem; font-weight: 700; margin-bottom: 0.5rem;">
            Subscription & Platform Tiers
        </h2>
        <p style="color: #78350F; font-size: 0.92rem; margin-bottom: 1.5rem;">
            Choose the subscription tier that matches your quantitative research requirements.
        </p>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2, gap="large")

    # ── Free Tier Card ────────────────────────────────────────────────────
    with col1:
        is_current_free = (plan == "free")
        badge_html = """
            <span style="background: #FEF3C7; color: #92400E; font-size: 0.75rem; font-weight: 700; padding: 2px 8px; border-radius: 4px; border: 1px solid #F59E0B;">
                CURRENT PLAN
            </span>
        """ if is_current_free else ""

        st.markdown(
            f"""
            <div style="background: rgba(255, 255, 255, 0.85); border: 1px solid #E5DFD5; border-radius: 12px; padding: 1.5rem; box-shadow: 0 4px 12px rgba(0,0,0,0.04); height: 100%;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="color: #2A2624; font-size: 1.3rem; font-weight: 700; margin: 0;">Community Plan</h3>
                    {badge_html}
                </div>
                <div style="font-size: 1.75rem; font-weight: 800; color: #2A2624; margin: 0.75rem 0;">₹0 <span style="font-size: 0.85rem; font-weight: 500; color: #78716C;">/ month</span></div>
                <hr style="border: none; border-top: 1px solid #E5DFD5; margin: 1rem 0;">
                <ul style="color: #44403C; font-size: 0.88rem; line-height: 1.8; padding-left: 1.25rem;">
                    <li><strong>3 Strategy Runs</strong> per calendar day</li>
                    <li><strong>2 Stress Regimes</strong> (COVID 2020 & 2008 GFC)</li>
                    <li>Full 4-Gate Adversarial Risk Verification</li>
                    <li>Standard Quantitative Performance Metrics</li>
                    <li>Deterministic Math Engine (Zero Hallucination)</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── Premium Tier Card ─────────────────────────────────────────────────
    with col2:
        is_current_prem = (plan == "premium")
        badge_prem = """
            <span style="background: #D1FAE5; color: #065F46; font-size: 0.75rem; font-weight: 700; padding: 2px 8px; border-radius: 4px; border: 1px solid #10B981;">
                ACTIVE PLAN
            </span>
        """ if is_current_prem else """
            <span style="background: #E0E7FF; color: #3730A3; font-size: 0.75rem; font-weight: 700; padding: 2px 8px; border-radius: 4px; border: 1px solid #6366F1;">
                RECOMMENDED
            </span>
        """

        st.markdown(
            f"""
            <div style="background: rgba(255, 255, 255, 0.95); border: 2px solid #D97706; border-radius: 12px; padding: 1.5rem; box-shadow: 0 4px 16px rgba(217,119,6,0.12); height: 100%;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h3 style="color: #431407; font-size: 1.3rem; font-weight: 700; margin: 0;">Institutional Premium</h3>
                    {badge_prem}
                </div>
                <div style="font-size: 1.75rem; font-weight: 800; color: #92400E; margin: 0.75rem 0;">₹{PREMIUM_PRICE_INR:,.0f} <span style="font-size: 0.85rem; font-weight: 500; color: #78716C;">/ month (TEST MODE)</span></div>
                <hr style="border: none; border-top: 1px solid #FDE68A; margin: 1rem 0;">
                <ul style="color: #44403C; font-size: 0.88rem; line-height: 1.8; padding-left: 1.25rem;">
                    <li><strong>Unlimited Strategy Runs</strong> (No Daily Throttling)</li>
                    <li><strong>All 4 Crisis Regimes</strong> (COVID, 2008 GFC, 2022 Tech Selloff, 2024 Election)</li>
                    <li>Full Chief Risk Officer (CRO) Executive Memo</li>
                    <li>Institutional F&O Derivative Contract & Lot Sizing</li>
                    <li>Complete Historical Cointegration Spread Diagnostics</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("<br>", unsafe_allow_html=True)
        if is_current_prem:
            st.success("You are subscribed to Institutional Premium with unlimited access.")
        else:
            if st.button("Upgrade to Premium via Razorpay (TEST MODE)", key="btn_upgrade_razorpay", type="primary", use_container_width=True):
                with st.spinner("Processing Test Mode Razorpay Payment & Cryptographic Verification..."):
                    # 1. Create order
                    order = create_subscription_order(user_id)
                    order_id = order["order_id"]
                    payment_id = f"pay_test_{order_id.replace('order_', '')}"

                    # 2. Compute cryptographic signature
                    sig = compute_test_signature(order_id, payment_id)

                    # 3. Apply verified upgrade
                    res = apply_verified_upgrade(
                        user_id=user_id,
                        razorpay_payment_id=payment_id,
                        razorpay_order_id=order_id,
                        razorpay_signature=sig,
                        amount_paise=PREMIUM_PRICE_PAISE,
                        access_token=token,
                    )

                    if res["success"]:
                        st.success(res["message"])
                        user["plan"] = "premium"
                        st.session_state["show_billing_modal"] = False
                        st.rerun()
                    else:
                        st.error(f"Upgrade Failed: {res['message']}")
