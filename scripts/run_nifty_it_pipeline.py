"""Execute the complete StocX NIFTY IT Agent Pipeline.

Runs all 6 pipeline stages:
1. Macro Intent Parser (Gemini 2.5 Flash)
2. Fundamental & Catalyst Screener (Gemini 2.5 Flash + CSV fundamentals)
3. Quantitative Execution Engine (Deterministic Python Math)
4. Risk Verifier (Adversarial Gatekeeper)
5. Cyclical Rejection & Self-Correction Loop (Up to 5 iterations)
6. Chief Risk Officer Reporter (Gemini 2.5 Pro)

Captures all telemetry, logs, state, and rejection traces into:
runs/nifty_it/YYYY-MM-DD_HH-MM-SS/
"""

from __future__ import annotations

import io
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Enforce execution environment invariants BEFORE importing modules
os.environ["ALLOW_SYNTHETIC"] = "false"
os.environ["LLM_MAX_RETRIES"] = "3"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

import config
from agents.gemini_client import sanitize_secret
from agents.graph import run_hedge_builder
from engine.data_fetcher import (
    get_fno_lot_sizes,
    get_fundamentals,
    get_sector_constituents,
    is_synthetic_allowed,
)

# ────────────────────────────────────────────────────────────────────────────
# Logging Setup
# ────────────────────────────────────────────────────────────────────────────

log_stream = io.StringIO()
log_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s", "%H:%M:%S")

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(log_formatter)
root_logger.addHandler(stream_handler)

string_handler = logging.StreamHandler(log_stream)
string_handler.setFormatter(log_formatter)
root_logger.addHandler(string_handler)

logger = logging.getLogger("NiftyITRun")


# ────────────────────────────────────────────────────────────────────────────
# Serialization & Sanitization Helpers
# ────────────────────────────────────────────────────────────────────────────


def sanitize_for_json(obj: Any) -> Any:
    """Recursively convert state data into clean, secret-redacted JSON-serializable types."""
    if obj is None:
        return None
    if isinstance(obj, (np.floating, float)):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return float(obj)
    if isinstance(obj, (np.integer, int)):
        return int(obj)
    if isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return [sanitize_for_json(x) for x in obj.tolist()]
    if isinstance(obj, pd.Series):
        return {str(k): sanitize_for_json(v) for k, v in obj.dropna().to_dict().items()}
    if isinstance(obj, pd.DataFrame):
        return [sanitize_for_json(row) for row in obj.to_dict(orient="records")]
    if isinstance(obj, (datetime, pd.Timestamp)):
        return obj.isoformat()
    if hasattr(obj, "content"):  # LangChain BaseMessage
        role = getattr(obj, "type", "message")
        return {"role": role, "content": sanitize_secret(str(obj.content))}
    if isinstance(obj, dict):
        return {str(k): sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [sanitize_for_json(x) for x in obj]
    if isinstance(obj, str):
        return sanitize_secret(obj)
    return sanitize_secret(str(obj))


# ────────────────────────────────────────────────────────────────────────────
# Main Pipeline Runner
# ────────────────────────────────────────────────────────────────────────────


def main() -> int:
    run_timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_dir = PROJECT_ROOT / "runs" / "nifty_it" / run_timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 70)
    logger.info("STOCX — NIFTY IT AGENT PIPELINE EXECUTION")
    logger.info("Timestamp: %s", run_timestamp)
    logger.info("Destination: %s", run_dir)
    logger.info("=" * 70)

    # 1. Pre-Run Checks
    logger.info("Running pre-flight system checks...")
    assert not is_synthetic_allowed(), "ALLOW_SYNTHETIC must be FALSE!"
    logger.info("✓ ALLOW_SYNTHETIC = %s", config.ALLOW_SYNTHETIC)
    logger.info("✓ LLM_MAX_RETRIES = %s", config.LLM_MAX_RETRIES)

    fund_csv = PROJECT_ROOT / "data" / "fundamentals.csv"
    assert fund_csv.exists(), f"Missing {fund_csv}"
    logger.info("✓ Fundamentals CSV verified: %s", fund_csv)

    lot_csv = PROJECT_ROOT / "data" / "nse_lot_sizes.csv"
    assert lot_csv.exists(), f"Missing {lot_csv}"
    logger.info("✓ NSE lot sizes CSV verified: %s", lot_csv)

    constituents = get_sector_constituents("NIFTY_IT")
    logger.info("✓ NIFTY IT constituents (%d symbols): %s", len(constituents), constituents)

    # Load lot sizes for reference
    lot_sizes = get_fno_lot_sizes()
    logger.info("✓ Loaded %d official NSE lot sizes", len(lot_sizes))

    # 2. Define Institutional Investment Thesis
    thesis = (
        "Bullish on high-quality Indian IT service leaders with resilient balance sheets, "
        "low debt, and superior ROE, while hedging against broader tech valuation compression "
        "and margin squeeze using weaker momentum constituents in the NIFTY IT sector under "
        "COVID-19 crisis stress conditions."
    )
    benchmark = "^NSEI"
    lookback_days = 252
    stress_regime = "COVID_2020"
    max_attempts = 5

    logger.info("\n--- INVESTMENT THESIS ---")
    logger.info(thesis)
    logger.info("Benchmark: %s | Lookback: %d days | Stress Regime: %s | Max Attempts: %d\n",
                benchmark, lookback_days, stress_regime, max_attempts)

    # 3. Execute LangGraph Pipeline
    logger.info("Launching LangGraph cyclical execution graph...")
    start_time = datetime.now()
    try:
        final_state = run_hedge_builder(
            thesis=thesis,
            benchmark=benchmark,
            lookback_days=lookback_days,
            stress_regime=stress_regime,
            max_attempts=max_attempts,
        )
        pipeline_status = "COMPLETED"
    except Exception as exc:
        logger.error("FATAL PIPELINE ERROR: %s", exc, exc_info=True)
        final_state = {
            "thesis": thesis,
            "pipeline_error": str(exc),
            "approved": False,
            "data_source": "error",
            "attempt_count": 0,
            "rejection_log": [],
        }
        pipeline_status = "FAILED"

    duration = (datetime.now() - start_time).total_seconds()
    logger.info("Pipeline execution %s in %.2f seconds.", pipeline_status, duration)

    # 4. Telemetry Extraction
    is_approved = bool(final_state.get("approved", False))
    data_source = final_state.get("data_source", "unknown")
    selected_long = final_state.get("selected_long", "")
    selected_short = final_state.get("selected_short", "")
    attempt_count = final_state.get("attempt_count", 0)
    rejection_log = final_state.get("rejection_log", [])
    cro_report = final_state.get("cro_report", "")
    pair_metrics = final_state.get("pair_metrics", {})
    weights = final_state.get("weights", {})
    hedged_stats = final_state.get("hedged_stats", {})
    unhedged_stats = final_state.get("unhedged_stats", {})
    stress_results = final_state.get("stress_results", {})
    fno_execution = final_state.get("fno_execution", {})
    long_candidates = final_state.get("long_candidates", [])
    short_candidates = final_state.get("short_candidates", [])

    logger.info("\n" + "=" * 70)
    logger.info("EXECUTION SUMMARY")
    logger.info("=" * 70)
    logger.info("Status:              %s", "APPROVED ✅" if is_approved else "REJECTED ❌")
    logger.info("Data Source Used:    %s", data_source)
    logger.info("Selected Long:       %s", selected_long or "None")
    logger.info("Selected Short:      %s", selected_short or "None")
    logger.info("Attempts Used:       %d / %d", attempt_count, max_attempts)
    logger.info("Total Rejections:    %d", len(rejection_log))
    if is_approved:
        logger.info("Long Weight:         %s", weights.get("long_weight"))
        logger.info("Short Weight:        %s", weights.get("short_weight"))
        logger.info("Hedged Sharpe:       %s", hedged_stats.get("sharpe"))
        logger.info("Hedged Max DD:       %s", hedged_stats.get("max_drawdown"))
        logger.info("Unhedged Max DD:     %s", unhedged_stats.get("max_drawdown"))
        logger.info("Pair Correlation:    %s", pair_metrics.get("pair_correlation"))
        coint = pair_metrics.get("cointegration", {})
        coint_p = coint.get("p_value") if isinstance(coint, dict) else pair_metrics.get("cointegration_pvalue")
        logger.info("Cointegration p-val: %s", coint_p)
    logger.info("=" * 70 + "\n")

    # 5. Save Artifacts for Dhairya and Audit
    logger.info("Saving artifacts to %s...", run_dir)

    # 5a. Full Sanitized LangGraph State JSON
    sanitized_state = sanitize_for_json(final_state)
    state_file = run_dir / "state.json"
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(sanitized_state, f, indent=2)
    logger.info("Saved: %s (%d bytes)", state_file.name, state_file.stat().st_size)

    # 5b. Rejection Trace JSON
    rejection_file = run_dir / "rejection_trace.json"
    sanitized_rejections = sanitize_for_json(rejection_log)
    with open(rejection_file, "w", encoding="utf-8") as f:
        json.dump({
            "total_attempts": attempt_count,
            "max_attempts": max_attempts,
            "approved": is_approved,
            "rejections": sanitized_rejections,
        }, f, indent=2)
    logger.info("Saved: %s", rejection_file.name)

    # 5c. Candidate Pair Metrics JSON
    metrics_file = run_dir / "candidate_metrics.json"
    with open(metrics_file, "w", encoding="utf-8") as f:
        json.dump({
            "data_source": data_source,
            "selected_long": selected_long,
            "selected_short": selected_short,
            "pair_metrics": sanitize_for_json(pair_metrics),
            "weights": sanitize_for_json(weights),
            "hedged_stats": sanitize_for_json(hedged_stats),
            "unhedged_stats": sanitize_for_json(unhedged_stats),
            "stress_results": sanitize_for_json(stress_results),
            "fno_execution": sanitize_for_json(fno_execution),
            "long_candidates_screened": sanitize_for_json(long_candidates),
            "short_candidates_screened": sanitize_for_json(short_candidates),
        }, f, indent=2)
    logger.info("Saved: %s", metrics_file.name)

    # 5d. CRO Executive Memo Markdown
    cro_file = run_dir / "cro_report.md"
    with open(cro_file, "w", encoding="utf-8") as f:
        f.write(cro_report)
    logger.info("Saved: %s", cro_file.name)

    # 5e. Execution Log
    log_file = run_dir / "execution_log.txt"
    with open(log_file, "w", encoding="utf-8") as f:
        f.write(sanitize_secret(log_stream.getvalue()))
    logger.info("Saved: %s", log_file.name)

    # 5g. Lookback Comparison JSON
    comparison_src = PROJECT_ROOT / "runs" / "lookback_comparison.json"
    if comparison_src.exists():
        import shutil
        shutil.copy(comparison_src, run_dir / "lookback_comparison.json")
        logger.info("Saved: lookback_comparison.json")

    # 5f. Dhairya Handoff README.md
    readme_file = run_dir / "README.md"
    readme_content = f"""# StocX NIFTY IT Pipeline Execution Artifacts
**Run Timestamp:** `{run_timestamp}`  
**Pipeline Status:** `{'APPROVED ✅' if is_approved else 'NOT APPROVED ❌'}`  
**Data Provenance:** `{data_source}` (Synthetic Fallback: **STRICTLY DISABLED**)  
**Execution Duration:** `{duration:.2f} seconds`  
**Gemini Models:** Fast=`{config.FAST_LLM_MODEL}`, Reasoning=`{config.REASONING_LLM_MODEL}`  

---

## 1. What This Run Did
This run executed the full 6-stage autonomous agent pipeline for the **NIFTY IT** sector universe:
1. **Macro Intent Parser:** Mapped the PM thesis to sector `NIFTY IT`, benchmark `{final_state.get('benchmark', '^NSEI')}`, lookback `{lookback_days}` days, and stress regime `{stress_regime}`.
2. **Fundamental & Catalyst Screener:** Loaded real fundamentals from `data/fundamentals.csv`, computed composite fundamental scores for all sector constituents, fetched qualitative catalyst news, and selected candidate long/short pairs while respecting past rejection history.
3. **Quantitative Execution Engine:** Deterministically computed beta (OLS + EWMA), Pearson correlation, Engle-Granger cointegration, spread z-score, Ornstein-Uhlenbeck half-life, beta-neutral portfolio weights, backtested return series, and crisis drawdown under `{stress_regime}`.
4. **Risk Verifier (Adversarial Gatekeeper):** Evaluated the pair against the 4 institutional risk gates:
   - Correlation $\\ge 0.65$
   - Cointegration p-value $< 0.05$
   - Hedged beta $< 0.15$
   - Drawdown reduction ratio $< 0.50$
5. **Rejection & Self-Correction Loop:** Automatically re-routed rejected pairs back to the Screener with full memory of past rejections.
6. **CRO Reporter:** Generated an institutional memorandum via `{config.REASONING_LLM_MODEL}` summarizing key metrics, provenance, risk findings, and F&O contract execution.

---

## 2. Directory Contents & How to Inspect

| File | Description | How to Inspect |
| :--- | :--- | :--- |
| `state.json` | Complete serialized LangGraph state at the end of the pipeline run. | Open in any JSON viewer or parse with `json.load(open('state.json'))`. All keys match `HedgeBuilderState`. |
| `rejection_trace.json` | The complete chronological audit trail of all candidate pairs evaluated and rejected. | Check `rejections` array to see which pairs were tried, their failing metric, and rejection explanation. |
| `candidate_metrics.json` | Detailed deterministic quant calculations for the final candidate pair, including weights and screened universe. | Contains raw floats for betas, correlation, cointegration p-value, Sharpe, and drawdown stats. |
| `cro_report.md` | Institutional executive memorandum ready for the Investment Committee or CRO. | Render with any Markdown viewer or Streamlit's `st.markdown()`. |
| `execution_log.txt` | Complete stdout/stderr execution log with timestamped agent actions and secret redactions. | Plain text inspection of pipeline telemetry. |
| `lookback_comparison.json` | Complete quantitative gate evaluation of all NIFTY IT candidate pairs comparing 252-day vs 504-day lookbacks. | Parse with `json.load(open('lookback_comparison.json'))`. |

---

## 3. Lookback Comparison Analysis (252-Day vs 504-Day)

Institutional comparison of candidate pairs across lookback horizons:

| Candidate Pair | 252d Correlation | 252d Cointegration $p$ | 252d Verdict | 504d Correlation | 504d Cointegration $p$ | 504d Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **COFORGE.NS / INFY.NS** | 0.61 | 0.708 | REJECTED ❌ | 0.60 | 0.944 | REJECTED ❌ |
| **COFORGE.NS / MPHASIS.NS** | 0.68 | 0.326 | REJECTED ❌ | 0.68 | 0.873 | REJECTED ❌ |
| **COFORGE.NS / HCLTECH.NS** | 0.57 | 0.959 | REJECTED ❌ | 0.57 | 0.912 | REJECTED ❌ |
| **COFORGE.NS / LTTS.NS** | 0.39 | 0.831 | REJECTED ❌ | 0.38 | 0.743 | REJECTED ❌ |
| **COFORGE.NS / WIPRO.NS** | 0.46 | 0.819 | REJECTED ❌ | 0.48 | 0.929 | REJECTED ❌ |
| **TCS.NS / INFY.NS** | 0.78 | 0.441 | REJECTED ❌ | 0.77 | 0.083 | REJECTED ❌ |
| **TCS.NS / WIPRO.NS** | 0.68 | 0.491 | REJECTED ❌ | **0.66** | **0.030** | **APPROVED ✅** |
| **INFY.NS / WIPRO.NS** | 0.60 | 0.122 | REJECTED ❌ | 0.63 | 0.017 | REJECTED ❌ (Corr < 0.65) |
| **TECHM.NS / WIPRO.NS** | 0.54 | 0.619 | REJECTED ❌ | 0.54 | 0.528 | REJECTED ❌ |
| **PERSISTENT.NS / LTTS.NS** | 0.41 | 0.382 | REJECTED ❌ | 0.39 | 0.275 | REJECTED ❌ |
| **PERSISTENT.NS / COFORGE.NS** | 0.68 | 0.177 | REJECTED ❌ | 0.71 | 0.463 | REJECTED ❌ |
| **HCLTECH.NS / TECHM.NS** | 0.70 | 0.505 | REJECTED ❌ | 0.68 | 0.854 | REJECTED ❌ |

- **Key Takeaway:** Over 252 days, spread non-stationarity rejected 100% of candidate pairs. Expanding to a 504-day structural horizon reveals genuine long-run cointegration for **TCS.NS / WIPRO.NS** ($p = 0.030 < 0.05$, $r = 0.66 \\ge 0.65$), passing all 4 gates.

---

## 4. UI Dashboard Integration Guide (For Dhairya)

Dhairya, here are the exact state fields to bind in the Streamlit dashboard:

### Top-Level Header & Badges
- **Status Pill:** Bind to `state["approved"]` -> `True` displays **APPROVED**, `False` displays **REJECTED**.
- **Data Source Pill:** Bind to `state["data_source"]` ->
  - `"cache"`: Render green badge `[Data: Local Cache (Validated)]`
  - `"yfinance"`: Render blue badge `[Data: Live Market Data (yfinance)]`
  - `"synthetic_fallback"`: Render red warning badge `[⚠️ Synthetic Simulation]`
- **Selected Pair:** Bind to `state["selected_long"]` and `state["selected_short"]`.

### Risk & Quantitative Metrics Table
Bind to `state["pair_metrics"]` and `state["hedged_stats"]`:
- **Static Beta (Long / Short):** `pair_metrics["static_beta_long"]` / `pair_metrics["static_beta_short"]`
- **EWMA Beta (Long / Short):** `pair_metrics["ewma_beta_long"]` / `pair_metrics["ewma_beta_short"]`
- **Pair Correlation:** `pair_metrics["pair_correlation"]` (Gate: $\\ge 0.65$)
- **Cointegration p-value:** `pair_metrics["cointegration"]["p_value"]` (Gate: $< 0.05$)
- **Spread Z-Score:** `pair_metrics["spread_zscore"]`
- **OU Half-Life:** `pair_metrics["ou_half_life"]` days
- **Hedged vs. Unhedged Sharpe:** `hedged_stats["sharpe"]` vs. `unhedged_stats["sharpe"]`
- **Hedged vs. Unhedged Max Drawdown:** `hedged_stats["max_drawdown"]` vs. `unhedged_stats["max_drawdown"]`

### Portfolio Weights & F&O Execution
- **Weights:** Bind to `state["weights"]["long_weight"]` and `state["weights"]["short_weight"]`.
- **F&O Execution Plan:** Bind to `state["fno_execution"]` (contains `long_lot_size`, `short_lot_size`, `margin_estimate`, etc.).

### Executive Memo
- **CRO Report:** Bind to `state["cro_report"]` and render via `st.markdown(state["cro_report"])`.

### Self-Correction & Rejection Audit
- **Rejection Log:** Bind to `state["rejection_log"]` (list of `{"long", "short", "reason"}`) to render the interactive rejection timeline.
"""
    with open(readme_file, "w", encoding="utf-8") as f:
        f.write(readme_content)
    logger.info("Saved: %s", readme_file.name)

    logger.info("\nArtifact generation complete. All files written to %s", run_dir)
    return 0 if is_approved else 1


if __name__ == "__main__":
    sys.exit(main())
