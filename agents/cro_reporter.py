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
* **Data integrity & provenance** – explicit disclosure of market data source.
* **Rejection audit trail** – every pair that was tried and why it failed.

If the pipeline was *not* approved (``max_attempts`` exhausted), the memo is
written as a *failure post-mortem* instead.
"""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from agents.gemini_client import extract_message_text, get_gemini_client, invoke_with_retry

from agents.state import HedgeBuilderState

logger = logging.getLogger(__name__)


def _get(state: Any, key: str, default: Any = None) -> Any:
    """Safely extract an attribute or dict key from state."""
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


# ────────────────────────────────────────────────────────────────────────────
# System prompts
# ────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT_APPROVED = """\
You are **CROReporterGPT**, the Chief Risk Officer of an institutional hedge
fund.  Write a professional executive memo summarising a SUCCESSFUL
market-neutral pair trade proposal.

The memo MUST include these sections (use markdown headings):

1. **Executive Summary** – 2-3 sentence verdict.
2. **Data Provenance & Integrity Disclosure** – Explicitly state whether the
   data source was live market data ("yfinance"), local CSV ("cache"), or
   "synthetic_fallback".  If "synthetic_fallback" was used, you MUST include a
   prominent bold warning stating that figures are simulated and CANNOT be
   deployed with real capital.
3. **Thesis Recap** – restate the PM's original thesis and how it was mapped
   to sector / benchmark / stress regime.
4. **Selected Pair & Rationale** – which stocks were picked and why.
5. **Key Metrics Dashboard** – present betas, cointegration stats, Sharpe
   ratios, drawdown, correlation, spread z-score, and OU half-life in a
   readable markdown table.
6. **Risk Assessment** – residual risks, monitoring triggers, and position
   limits.
7. **Stress Test Narrative** – how the hedged pair performed in the stress
   regime.  Was the hedge effective?
8. **F&O Execution Plan** – lot sizes, margin requirements, and recommended
   entry strategy.
9. **Pair Selection Audit Trail** – list every pair that was tried, whether
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
2. **Data Provenance Disclosure** – disclose the data source ("yfinance",
   "cache", or "synthetic_fallback") and any simulation warnings.
3. **Thesis Recap** – what was attempted.
4. **Attempt Log** – for EACH attempted pair, summarise the metrics and
   explain why it was rejected.
5. **Pattern Analysis** – are there common failure modes across attempts?
6. **Recommendations** – what should the PM consider changing (sector,
   lookback, benchmark, thesis refinement)?

Rules:
- Reference exact numbers from the data.
- Do NOT recompute any numbers.
- Professional tone.
"""


# ────────────────────────────────────────────────────────────────────────────
# Node function
# ────────────────────────────────────────────────────────────────────────────


def cro_reporter_node(state: HedgeBuilderState | dict[str, Any]) -> dict:
    """Generate the final CRO executive memo.

    This function is the terminal analytical node in the graph.  It
    compiles all state data into a prompt and asks the LLM to write a
    structured institutional memo.

    Args:
        state: Full graph state with all quant results, verification
            outcomes, data provenance, and the rejection log.

    Returns:
        Partial state dict setting ``cro_report`` and appending the report
        as an assistant message.
    """
    is_approved = bool(_get(state, "approved", False))
    data_source = _get(state, "data_source", "yfinance")
    attempt_count = _get(state, "attempt_count", 0)
    max_attempts = _get(state, "max_attempts", 5)

    logger.info(
        "CROReporter ▸ Generating %s memo (attempts used: %d/%d, data_source: %s)",
        "APPROVED" if is_approved else "FAILURE",
        attempt_count,
        max_attempts,
        data_source,
    )

    # ── Build comprehensive data payload for the LLM ───────────────────
    data_payload = _build_data_payload(state)
    system_prompt = _SYSTEM_PROMPT_APPROVED if is_approved else _SYSTEM_PROMPT_FAILED

    try:
        llm = get_gemini_client(
            model_type="reasoning",
            temperature=0.4,
        )
        response = invoke_with_retry(
            llm,
            [
                SystemMessage(content=system_prompt),
                HumanMessage(content=data_payload),
            ],
        )
        cro_report = extract_message_text(response)
        logger.info("CROReporter ▸ Memo generated (%d chars).", len(cro_report))

    except Exception as exc:
        logger.error("CROReporter ▸ LLM call failed: %s", exc)
        cro_report = _fallback_report(state)

    # Guardrail: guarantee synthetic fallback is never silently disguised
    if data_source == "synthetic_fallback" and "SYNTHETIC" not in cro_report.upper():
        cro_report = (
            "> ⚠️ **CRITICAL DATA INTEGRITY WARNING: SYNTHETIC DATA**\n"
            "> Live market data was unavailable for this analysis. All returns, betas, cointegration,\n"
            "> and risk metrics were generated from synthetic fallback series and CANNOT be traded.\n\n"
            + cro_report
        )

    return {
        "cro_report": cro_report,
        "data_source": data_source,
        "messages": [{"role": "assistant", "content": cro_report}],
    }


# ────────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────────


def _build_data_payload(state: HedgeBuilderState | dict[str, Any]) -> str:
    """Compile all graph state data into a structured prompt for the LLM.

    Args:
        state: Full graph state.

    Returns:
        Formatted markdown string containing every data point the LLM needs.
    """
    pm = _get(state, "pair_metrics", {}) or {}
    hs = _get(state, "hedged_stats", {}) or {}
    us = _get(state, "unhedged_stats", {}) or {}
    sr = _get(state, "stress_results", {}) or {}
    wt = _get(state, "weights", {}) or {}
    fno = _get(state, "fno_execution", {}) or {}
    data_source = _get(state, "data_source", "yfinance")
    rejection_log = _get(state, "rejection_log", []) or []
    is_approved = bool(_get(state, "approved", False))
    selected_long = _get(state, "selected_long", "")
    selected_short = _get(state, "selected_short", "")
    stress_regime = _get(state, "stress_regime", "COVID_2020")
    thesis = _get(state, "thesis", "")
    target_sector = _get(state, "target_sector", "")
    benchmark = _get(state, "benchmark", "^NSEI")
    lookback_days = _get(state, "lookback_days", 252)
    attempt_count = _get(state, "attempt_count", 0)
    max_attempts = _get(state, "max_attempts", 5)

    data_warning = ""
    if data_source == "synthetic_fallback":
        data_warning = (
            "\n> ⚠️ **CRITICAL WARNING:** Market data source is SYNTHETIC_FALLBACK. "
            "Live market data fetching was unavailable, and price series were generated via simulation. "
            "These metrics CANNOT be relied upon for live deployment or execution.\n"
        )

    # ── Rejection audit trail ──────────────────────────────────────────
    audit_lines: list[str] = []
    for i, entry in enumerate(rejection_log, 1):
        audit_lines.append(
            f"### Attempt {i}: {entry.get('long', '?')} / {entry.get('short', '?')}\n"
            f"- **Engine reason:** {entry.get('reason', 'N/A')}\n"
            f"- **Diagnostic:** {entry.get('llm_diagnostic', 'N/A')}\n"
        )
    audit_section = "\n".join(audit_lines) if audit_lines else "_First attempt succeeded._"

    # ── Final pair section (only if approved) ──────────────────────────
    final_pair_section = ""
    if is_approved:
        coint_dict = pm.get("cointegration", {})
        coint_p = coint_dict.get("p_value", "N/A") if isinstance(coint_dict, dict) else "N/A"

        final_pair_section = f"""
## Approved Pair
- **Long:** {selected_long}
- **Short:** {selected_short}

## Key Metrics
| Metric | Value |
|--------|-------|
| Static β (long) | {pm.get('static_beta_long', 'N/A')} |
| Static β (short) | {pm.get('static_beta_short', 'N/A')} |
| EWMA β (long) | {pm.get('ewma_beta_long', 'N/A')} |
| EWMA β (short) | {pm.get('ewma_beta_short', 'N/A')} |
| Pair Correlation | {pm.get('pair_correlation', 'N/A')} |
| Cointegration p-value | {coint_p} |
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

## Stress Test ({stress_regime})
- Max drawdown: {sr.get('max_drawdown_pct', 'N/A')}%
- Recovery days: {sr.get('recovery_days', 'N/A')}

## F&O Execution Plan
{_format_fno(fno)}
"""

    return f"""
# CRO Report Data

## Thesis
{thesis}

## Data Provenance
- Market Data Source: {data_source}
{data_warning}
## Macro Parameters
- Sector: {target_sector}
- Benchmark: {benchmark}
- Lookback: {lookback_days} days
- Stress regime: {stress_regime}

## Attempts Used: {attempt_count} / {max_attempts}
## Final Verdict: {"APPROVED ✅" if is_approved else "NOT APPROVED ❌"}

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


def _fallback_report(state: HedgeBuilderState | dict[str, Any]) -> str:
    """Generate a minimal plaintext report when the LLM is unavailable.

    Args:
        state: Full graph state.

    Returns:
        A basic text summary.
    """
    is_approved = bool(_get(state, "approved", False))
    status = "APPROVED" if is_approved else "NOT APPROVED"
    data_source = _get(state, "data_source", "yfinance")
    thesis = _get(state, "thesis", "")
    target_sector = _get(state, "target_sector", "")
    selected_long = _get(state, "selected_long", "")
    selected_short = _get(state, "selected_short", "")
    attempt_count = _get(state, "attempt_count", 0)
    max_attempts = _get(state, "max_attempts", 5)
    rejection_log = _get(state, "rejection_log", []) or []

    warning_block = ""
    if data_source == "synthetic_fallback":
        warning_block = (
            "\n> ⚠️ **CRITICAL DATA INTEGRITY WARNING:** This report was generated using "
            "SYNTHETIC/SIMULATED price data because live market data was unavailable. "
            "The results are NOT based on genuine market prices and CANNOT be deployed.\n\n"
        )
    return (
        f"# CRO Report (Fallback – LLM Unavailable)\n\n"
        f"**Status:** {status}\n"
        f"**Data Source:** {data_source}\n"
        f"{warning_block}"
        f"**Thesis:** {thesis}\n"
        f"**Sector:** {target_sector}\n"
        f"**Long:** {selected_long}\n"
        f"**Short:** {selected_short}\n"
        f"**Attempts:** {attempt_count}/{max_attempts}\n"
        f"**Rejections:** {len(rejection_log)}\n\n"
        f"_Full LLM-generated memo could not be produced.  "
        f"See the message history for detailed node outputs._"
    )
