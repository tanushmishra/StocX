"""Chief Risk Officer Reporter – Executive memo generator node.

This agent uses **Gemini 2.5 Pro** to produce a comprehensive, plain-English
institutional memo that a non-technical CRO or investment committee could read
and act on.

The memo includes:

* **Thesis recap** – what the PM wanted and how we interpreted it.
* **Pair rationale** – why these two stocks were chosen.
* **Key metrics dashboard** – betas, cointegration, Sharpe, drawdown, etc.
* **Risk assessment** – residual risks and mitigation.
* **Stress-test narrative** – how the pair behaved in the chosen regime.
* **F&O execution plan** – lot sizes and margin requirements.
* **Rejection audit trail** – every pair that was tried and why it failed.

If the pipeline was *not* approved (``max_attempts`` exhausted), the memo is
written as a *failure post-mortem* instead.
"""

from __future__ import annotations

import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from agents.state import HedgeBuilderState

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────────────────────
# System prompts
# ────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT_APPROVED = """\
You are **CROReporterGPT**, the Chief Risk Officer of an institutional hedge
fund.  Write a professional executive memo summarising a SUCCESSFUL
market-neutral pair trade proposal.

The memo MUST include these sections (use markdown headings):

1. **Executive Summary** – 2-3 sentence verdict.
2. **Thesis Recap** – restate the PM's original thesis and how it was mapped
   to sector / benchmark / stress regime.
3. **Selected Pair & Rationale** – which stocks were picked and why.
4. **Key Metrics Dashboard** – present betas, cointegration stats, Sharpe
   ratios, drawdown, correlation, spread z-score, and OU half-life in a
   readable markdown table.
5. **Risk Assessment** – residual risks, monitoring triggers, and position
   limits.
6. **Stress Test Narrative** – how the hedged pair performed in the stress
   regime.  Was the hedge effective?
7. **F&O Execution Plan** – lot sizes, margin requirements, and recommended
   entry strategy.
8. **Pair Selection Audit Trail** – list every pair that was tried, whether
   it passed or failed, and why.

Rules:
- Be precise.  Reference exact numbers from the data provided.
- Do NOT recompute any numbers.
- Use professional, institutional tone.
- Format for readability: tables, bullet points, bold for key figures.
"""

_SYSTEM_PROMPT_FAILED = """\
You are **CROReporterGPT**, the Chief Risk Officer of an institutional hedge
fund.  Write a professional executive memo summarising a FAILED pair-trade
search.  The system exhausted all attempts without finding an approvable pair.

The memo MUST include:

1. **Executive Summary** – state clearly that no viable pair was found.
2. **Thesis Recap** – what was attempted.
3. **Attempt Log** – for EACH attempted pair, summarise the metrics and
   explain why it was rejected.
4. **Pattern Analysis** – are there common failure modes across attempts?
5. **Recommendations** – what should the PM consider changing (sector,
   lookback, benchmark, thesis refinement)?

Rules:
- Reference exact numbers from the data.
- Do NOT recompute any numbers.
- Professional tone.
"""


# ────────────────────────────────────────────────────────────────────────────
# Node function
# ────────────────────────────────────────────────────────────────────────────


def cro_reporter_node(state: HedgeBuilderState) -> dict:
    """Generate the final CRO executive memo.

    This function is the terminal analytical node in the graph.  It
    compiles all state data into a prompt and asks the LLM to write a
    structured institutional memo.

    Args:
        state: Full graph state with all quant results, verification
            outcomes, and the rejection log.

    Returns:
        Partial state dict setting ``cro_report`` and appending the report
        as an assistant message.
    """
    is_approved = state.approved

    logger.info(
        "CROReporter ▸ Generating %s memo (attempts used: %d/%d)",
        "APPROVED" if is_approved else "FAILURE",
        state.attempt_count,
        state.max_attempts,
    )

    # ── Build comprehensive data payload for the LLM ───────────────────
    data_payload = _build_data_payload(state)
    system_prompt = _SYSTEM_PROMPT_APPROVED if is_approved else _SYSTEM_PROMPT_FAILED

    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.5-pro",
            temperature=0.4,
        )
        response = llm.invoke(
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=data_payload),
            ]
        )
        cro_report = response.content
        logger.info("CROReporter ▸ Memo generated (%d chars).", len(cro_report))

    except Exception as exc:
        logger.error("CROReporter ▸ LLM call failed: %s", exc)
        cro_report = _fallback_report(state)

    return {
        "cro_report": cro_report,
        "messages": [{"role": "assistant", "content": cro_report}],
    }


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────


def _build_data_payload(state: HedgeBuilderState) -> str:
    """Compile all graph state data into a structured prompt for the LLM.

    Args:
        state: Full graph state.

    Returns:
        Formatted markdown string containing every data point the LLM needs.
    """
    pm = state.pair_metrics
    hs = state.hedged_stats
    us = state.unhedged_stats
    sr = state.stress_results
    wt = state.weights
    fno = state.fno_execution

    # ── Rejection audit trail ──────────────────────────────────────────
    audit_lines: list[str] = []
    for i, entry in enumerate(state.rejection_log, 1):
        audit_lines.append(
            f"### Attempt {i}: {entry.get('long', '?')} / {entry.get('short', '?')}\n"
            f"- **Engine reason:** {entry.get('reason', 'N/A')}\n"
            f"- **Diagnostic:** {entry.get('llm_diagnostic', 'N/A')}\n"
        )
    audit_section = "\n".join(audit_lines) if audit_lines else "_First attempt succeeded._"

    # ── Final pair section (only if approved) ──────────────────────────
    final_pair_section = ""
    if state.approved:
        final_pair_section = f"""
## Approved Pair
- **Long:** {state.selected_long}
- **Short:** {state.selected_short}

## Key Metrics
| Metric | Value |
|--------|-------|
| Static β (long) | {pm.get('static_beta_long', 'N/A')} |
| Static β (short) | {pm.get('static_beta_short', 'N/A')} |
| EWMA β (long) | {pm.get('ewma_beta_long', 'N/A')} |
| EWMA β (short) | {pm.get('ewma_beta_short', 'N/A')} |
| Pair Correlation | {pm.get('pair_correlation', 'N/A')} |
| Cointegration p-value | {pm.get('cointegration', {{}}).get('p_value', 'N/A')} |
| Spread z-score | {pm.get('spread_zscore', 'N/A')} |
| OU Half-life | {pm.get('ou_half_life', 'N/A')} days |
| Hedged Sharpe | {hs.get('sharpe', 'N/A')} |
| Hedged Max Drawdown | {hs.get('max_drawdown', 'N/A')} |
| Hedged Annual Return | {hs.get('annual_return', 'N/A')} |
| Hedged Volatility | {hs.get('volatility', 'N/A')} |
| Unhedged Sharpe | {us.get('sharpe', 'N/A')} |
| Unhedged Max Drawdown | {us.get('max_drawdown', 'N/A')} |

## Portfolio Weights
- Long weight: {wt.get('long_weight', 'N/A')}
- Short weight: {wt.get('short_weight', 'N/A')}

## Stress Test ({state.stress_regime})
- Max drawdown: {sr.get('max_drawdown_pct', 'N/A')}%
- Recovery days: {sr.get('recovery_days', 'N/A')}

## F&O Execution Plan
{_format_fno(fno)}
"""

    return f"""
# CRO Report Data

## Thesis
{state.thesis}

## Macro Parameters
- Sector: {state.target_sector}
- Benchmark: {state.benchmark}
- Lookback: {state.lookback_days} days
- Stress regime: {state.stress_regime}

## Attempts Used: {state.attempt_count} / {state.max_attempts}
## Final Verdict: {"APPROVED ✅" if state.approved else "NOT APPROVED ❌"}

{final_pair_section}

## Pair Selection Audit Trail
{audit_section}
"""


def _format_fno(fno: dict) -> str:
    """Format the F&O execution dict into readable lines.

    Args:
        fno: Dict from ``engine.portfolio.convert_to_fno_lots()``.

    Returns:
        Bullet-point formatted string.
    """
    if not fno:
        return "_F&O data not available._"

    lines: list[str] = []
    for key, value in fno.items():
        # Convert snake_case to Title Case for readability
        display_key = key.replace("_", " ").title()
        lines.append(f"- **{display_key}:** {value}")
    return "\n".join(lines)


def _fallback_report(state: HedgeBuilderState) -> str:
    """Generate a minimal plaintext report when the LLM is unavailable.

    Args:
        state: Full graph state.

    Returns:
        A basic text summary.
    """
    status = "APPROVED" if state.approved else "NOT APPROVED"
    return (
        f"# CRO Report (Fallback – LLM Unavailable)\n\n"
        f"**Status:** {status}\n"
        f"**Thesis:** {state.thesis}\n"
        f"**Sector:** {state.target_sector}\n"
        f"**Long:** {state.selected_long}\n"
        f"**Short:** {state.selected_short}\n"
        f"**Attempts:** {state.attempt_count}/{state.max_attempts}\n"
        f"**Rejections:** {len(state.rejection_log)}\n\n"
        f"_Full LLM-generated memo could not be produced.  "
        f"See the message history for detailed node outputs._"
    )
