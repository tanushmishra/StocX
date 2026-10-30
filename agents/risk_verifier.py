"""Adversarial Risk Verifier – LLM-enhanced gatekeeper node.

This agent acts as the portfolio's last line of defence before a pair trade
is approved.  It:

1. Calls ``engine.verifier.verify_pair()`` – a deterministic rule-based check
   that evaluates cointegration quality, beta stability, spread behaviour,
   backtest metrics, and stress-test drawdown.
2. If the engine **rejects** the pair, uses **Gemini 2.5 Pro** to write a
   detailed diagnostic explaining *why* the pair failed and *what* the
   Screener should look for next time.  Then routes back to the Screener
   (the self-correction loop).
3. If the engine **approves** the pair, uses the LLM to write a brief
   confirmation summary and routes forward to the CRO Reporter.
4. If ``max_attempts`` is exhausted, marks the run as unapproved and routes
   to the CRO Reporter with a failure summary.

**Architecture invariant**: The LLM reads the numbers but NEVER computes them.
All quantitative gates are evaluated by ``engine.verifier.verify_pair()``.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from agents.state import HedgeBuilderState

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# System prompt
# ────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT_REJECTION = """\
You are **RiskAdversaryGPT**, a senior risk officer reviewing a failed pair
trade proposal.

You will receive the quantitative verification report produced by the
deterministic engine.  Your job:

1. Explain IN PLAIN ENGLISH why the pair failed each gate that it failed.
2. Identify the *single most critical flaw* in the pair.
3. Suggest what characteristics the NEXT pair should have to avoid this
   failure mode (be specific – e.g. "look for lower beta spread" or "need
   stronger cointegration with p < 0.05").

Rules:
- Do NOT recompute any numbers.  Reference only the values in the report.
- Be concise: 3-5 sentences per point.
- Use bullet points.
"""

_SYSTEM_PROMPT_APPROVAL = """\
You are **RiskAdversaryGPT**, a senior risk officer.  The pair trade has
PASSED all verification gates.

Write a brief (3-4 sentence) confirmation note summarising:
1. Which gates were the tightest (closest to threshold).
2. Any residual risk the portfolio manager should monitor.

Reference only the numbers in the report.  Do NOT recompute anything.
"""


# ────────────────────────────────────────────────────────────────────────────
# Node function
# ────────────────────────────────────────────────────────────────────────────


def risk_verifier_node(state: HedgeBuilderState) -> dict:
    """Verify the current pair and either approve or trigger a retry loop.

    This function is registered as a **LangGraph node**.  The routing decision
    is made by a downstream conditional edge that inspects ``approved`` and
    ``attempt_count``.

    Args:
        state: Current graph state containing ``selected_long``,
            ``selected_short``, ``pair_metrics``, ``hedged_stats``,
            ``stress_results``, and the current ``attempt_count``.

    Returns:
        Partial state dict updating ``verifier_result``, ``approved``,
        ``attempt_count``, and (on rejection) appending to ``rejection_log``.
    """
    long_ticker = state.selected_long
    short_ticker = state.selected_short
    attempt = state.attempt_count

    logger.info(
        "RiskVerifier ▸ Verifying pair LONG=%s SHORT=%s (attempt %d/%d)",
        long_ticker,
        short_ticker,
        attempt + 1,
        state.max_attempts,
    )

    # ── 1. Run deterministic verification ──────────────────────────────
    try:
        from engine.verifier import verify_pair

        verifier_result: dict[str, Any] = verify_pair(
            long_ticker=long_ticker,
            short_ticker=short_ticker,
            pair_metrics=state.pair_metrics,
            hedged_stats=state.hedged_stats,
            stress_results=state.stress_results,
            weights=state.weights,
        )
    except Exception as exc:
        logger.error("RiskVerifier ▸ Engine verification failed: %s", exc)
        verifier_result = {
            "approved": False,
            "reason": f"Engine verification crashed: {exc}",
            "gates": {},
        }

    is_approved = verifier_result.get("approved", False)
    reason = verifier_result.get("reason", "")

    logger.info(
        "RiskVerifier ▸ Engine verdict: %s | Reason: %s",
        "APPROVED" if is_approved else "REJECTED",
        reason[:200],
    )

    # ── 2. Format the full report for the LLM ─────────────────────────
    report_text = _build_report(state, verifier_result)

    # ── 3. Get LLM diagnostic / confirmation ──────────────────────────
    llm_commentary = _get_llm_commentary(is_approved, report_text)

    # ── 4. Build partial state update ──────────────────────────────────
    new_attempt_count = attempt + 1  # always increment (we just completed an attempt)

    if is_approved:
        summary_msg = (
            f"**Risk Verifier – APPROVED (Attempt {new_attempt_count})**\n\n"
            f"{llm_commentary}"
        )
        return {
            "verifier_result": verifier_result,
            "approved": True,
            "attempt_count": new_attempt_count,
            "messages": [{"role": "assistant", "content": summary_msg}],
        }
    else:
        # ── Rejection path ─────────────────────────────────────────────
        rejection_entry = {
            "long": long_ticker,
            "short": short_ticker,
            "reason": reason,
            "attempt": new_attempt_count,
            "llm_diagnostic": llm_commentary,
        }

        summary_msg = (
            f"**Risk Verifier – REJECTED (Attempt {new_attempt_count}/{state.max_attempts})**\n\n"
            f"**Engine reason:** {reason}\n\n"
            f"**Diagnostic:**\n{llm_commentary}"
        )

        return {
            "verifier_result": verifier_result,
            "approved": False,
            "attempt_count": new_attempt_count,
            "rejection_log": state.rejection_log + [rejection_entry],
            "messages": [{"role": "assistant", "content": summary_msg}],
        }


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────


def _build_report(state: HedgeBuilderState, verifier_result: dict) -> str:
    """Assemble a comprehensive text report for the LLM to read.

    Args:
        state: Full graph state with all quant results.
        verifier_result: Output of ``engine.verifier.verify_pair()``.

    Returns:
        A formatted markdown string with all key numbers.
    """
    pm = state.pair_metrics
    hs = state.hedged_stats
    us = state.unhedged_stats
    sr = state.stress_results
    wt = state.weights

    lines = [
        f"## Verification Report: {state.selected_long} (L) / {state.selected_short} (S)",
        "",
        "### Betas",
        f"- Static β (long): {pm.get('static_beta_long', 'N/A')}",
        f"- Static β (short): {pm.get('static_beta_short', 'N/A')}",
        f"- EWMA β (long): {pm.get('ewma_beta_long', 'N/A')}",
        f"- EWMA β (short): {pm.get('ewma_beta_short', 'N/A')}",
        "",
        "### Cointegration",
        f"- Engle-Granger p-value: {pm.get('cointegration', {}).get('p_value', 'N/A')}",
        f"- Spread z-score: {pm.get('spread_zscore', 'N/A')}",
        f"- OU half-life: {pm.get('ou_half_life', 'N/A')} days",
        f"- Pair correlation: {pm.get('pair_correlation', 'N/A')}",
        "",
        "### Portfolio Weights",
        f"- Long weight: {wt.get('long_weight', 'N/A')}",
        f"- Short weight: {wt.get('short_weight', 'N/A')}",
        "",
        "### Backtest – Hedged",
        f"- Sharpe: {hs.get('sharpe', 'N/A')}",
        f"- Max drawdown: {hs.get('max_drawdown', 'N/A')}",
        f"- Annual return: {hs.get('annual_return', 'N/A')}",
        f"- Volatility: {hs.get('volatility', 'N/A')}",
        "",
        "### Backtest – Unhedged (long only)",
        f"- Sharpe: {us.get('sharpe', 'N/A')}",
        f"- Max drawdown: {us.get('max_drawdown', 'N/A')}",
        "",
        "### Stress Test",
        f"- Regime: {state.stress_regime}",
        f"- Max drawdown: {sr.get('max_drawdown_pct', 'N/A')}%",
        f"- Recovery days: {sr.get('recovery_days', 'N/A')}",
        "",
        "### Engine Verdict",
        f"- Approved: {verifier_result.get('approved', 'N/A')}",
        f"- Reason: {verifier_result.get('reason', 'N/A')}",
        f"- Gate details: {verifier_result.get('gates', {})}",
    ]
    return "\n".join(lines)


def _get_llm_commentary(is_approved: bool, report_text: str) -> str:
    """Ask the LLM for a diagnostic (rejection) or confirmation (approval).

    Args:
        is_approved: Whether the engine approved the pair.
        report_text: The full verification report markdown.

    Returns:
        LLM-generated commentary string.  Falls back to a simple message
        if the LLM call fails.
    """
    system_prompt = _SYSTEM_PROMPT_APPROVAL if is_approved else _SYSTEM_PROMPT_REJECTION

    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-pro",
            temperature=0.3,
        )
        response = llm.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=report_text),
            ]
        )
        return response.content
    except Exception as exc:
        logger.error("RiskVerifier ▸ LLM commentary failed: %s", exc)
        if is_approved:
            return "Pair approved by engine.  LLM commentary unavailable."
        else:
            return f"Pair rejected by engine.  LLM commentary unavailable.  Engine reason: {report_text}"
