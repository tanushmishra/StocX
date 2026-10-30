"""Compare 252-day vs 504-day lookback windows on NIFTY IT candidate pairs.

Evaluates deterministic quant engine metrics:
- Correlation
- Cointegration p-value & critical values
- Beta (Static + EWMA)
- Beta-neutral weights
- Spread z-score & OU half-life
- Hedged & Unhedged Max Drawdown
- Verifier gate outcomes

Saves output to lookback_comparison.json.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

os.environ["ALLOW_SYNTHETIC"] = "false"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from engine.beta_calculator import (
    compute_ewma_beta,
    compute_static_beta,
)
from engine.cointegration import (
    compute_spread_zscore,
    engle_granger_test,
    ou_half_life,
)
from engine.data_fetcher import (
    fetch_prices,
    get_sector_constituents,
    get_fundamentals,
    is_synthetic_allowed,
)
from engine.backtester import backtest_pair
from engine.portfolio import (
    compute_beta_neutral_weights,
    compute_correlation_matrix,
)
from engine.verifier import verify_pair

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("LookbackComparison")


def evaluate_pair_window(
    long_ticker: str,
    short_ticker: str,
    benchmark: str,
    lookback_days: int,
) -> dict[str, Any]:
    """Compute all quant metrics and verification gates for a specific pair and lookback."""
    result: dict[str, Any] = {
        "long": long_ticker,
        "short": short_ticker,
        "lookback_days": lookback_days,
        "data_available": False,
        "rows": 0,
        "data_source": "none",
        "gates": {},
        "approved": False,
        "failure_reason": "",
    }

    try:
        prices = fetch_prices([long_ticker, short_ticker, benchmark], lookback_days=lookback_days)
        result["data_available"] = True
        result["rows"] = len(prices)
        result["data_source"] = prices.attrs.get("data_source", "unknown")
        result["start_date"] = prices.index[0].strftime("%Y-%m-%d")
        result["end_date"] = prices.index[-1].strftime("%Y-%m-%d")
    except Exception as exc:
        result["failure_reason"] = f"Price fetch failed: {exc}"
        return result

    returns = prices.pct_change().dropna()
    if len(returns) < 30:
        result["failure_reason"] = f"Insufficient return observations ({len(returns)} rows)"
        return result

    long_r = returns[long_ticker]
    short_r = returns[short_ticker]
    mkt_r = returns[benchmark]

    # Betas
    beta_long = compute_static_beta(long_r, mkt_r)
    beta_short = compute_static_beta(short_r, mkt_r)
    ewma_long_s = compute_ewma_beta(long_r, mkt_r)
    ewma_short_s = compute_ewma_beta(short_r, mkt_r)
    ewma_long = float(ewma_long_s.dropna().iloc[-1]) if not ewma_long_s.dropna().empty else beta_long
    ewma_short = float(ewma_short_s.dropna().iloc[-1]) if not ewma_short_s.dropna().empty else beta_short

    # Correlation
    corr_mat = compute_correlation_matrix(returns[[long_ticker, short_ticker, benchmark]])
    pair_corr = float(corr_mat.loc[long_ticker, short_ticker])

    # Cointegration
    coint_res = engle_granger_test(prices[long_ticker], prices[short_ticker])
    coint_p = coint_res.get("p_value", 1.0)
    hedge_ratio = coint_res.get("hedge_ratio", 1.0)

    # Spread dynamics
    zscore_s = compute_spread_zscore(prices[long_ticker], prices[short_ticker], window=min(30, len(prices) // 2))
    current_zscore = float(zscore_s.dropna().iloc[-1]) if not zscore_s.dropna().empty else 0.0
    spread = np.log(prices[long_ticker]) - np.log(prices[short_ticker])
    hl = ou_half_life(spread)

    # Weights
    weights = compute_beta_neutral_weights(beta_long, beta_short)
    w_long = weights["long"]
    w_short = weights["short"]

    # Backtest
    bt_res = backtest_pair(long_r, short_r, mkt_r, w_long, w_short)
    hedged_stats = bt_res["hedged_metrics"]
    unhedged_stats = bt_res["unhedged_metrics"]

    pair_metrics = {
        "static_beta_long": beta_long,
        "static_beta_short": beta_short,
        "ewma_beta_long": ewma_long,
        "ewma_beta_short": ewma_short,
        "pair_correlation": pair_corr,
        "correlation": pair_corr,
        "cointegration": coint_res,
        "cointegration_pvalue": coint_p,
        "spread_zscore": current_zscore,
        "ou_half_life": hl,
    }

    # Verify gates
    v_res = verify_pair(
        pair_metrics=pair_metrics,
        hedged_stats=hedged_stats,
        unhedged_stats=unhedged_stats,
        stress_results={},
        weights=weights,
    )

    result.update({
        "pair_correlation": pair_corr,
        "cointegration_pvalue": coint_p,
        "hedge_ratio": hedge_ratio,
        "ou_half_life": hl,
        "spread_zscore": current_zscore,
        "static_beta_long": beta_long,
        "static_beta_short": beta_short,
        "w_long": w_long,
        "w_short": w_short,
        "hedged_sharpe": hedged_stats.get("sharpe_ratio"),
        "hedged_max_dd": hedged_stats.get("max_drawdown"),
        "unhedged_max_dd": unhedged_stats.get("max_drawdown"),
        "gates": v_res.get("gates", {}),
        "approved": v_res.get("approved", False),
        "failure_reason": v_res.get("reason", ""),
    })

    return result


def main():
    logger.info("Starting Lookback Window Comparison (252 vs 504 days)...")
    benchmark = "^NSEI"

    # Screened candidate pairs across NIFTY IT
    candidate_pairs = [
        ("COFORGE.NS", "INFY.NS"),
        ("COFORGE.NS", "MPHASIS.NS"),
        ("COFORGE.NS", "HCLTECH.NS"),
        ("COFORGE.NS", "LTTS.NS"),
        ("COFORGE.NS", "WIPRO.NS"),
        ("TCS.NS", "INFY.NS"),
        ("TCS.NS", "WIPRO.NS"),
        ("INFY.NS", "WIPRO.NS"),
        ("TECHM.NS", "WIPRO.NS"),
        ("PERSISTENT.NS", "LTTS.NS"),
        ("PERSISTENT.NS", "COFORGE.NS"),
        ("HCLTECH.NS", "TECHM.NS"),
    ]

    comparison_results = []

    for long_t, short_t in candidate_pairs:
        logger.info("Evaluating pair: %s / %s", long_t, short_t)
        res_252 = evaluate_pair_window(long_t, short_t, benchmark, lookback_days=252)
        res_504 = evaluate_pair_window(long_t, short_t, benchmark, lookback_days=504)

        comparison_results.append({
            "pair": f"{long_t} / {short_t}",
            "long": long_t,
            "short": short_t,
            "window_252": res_252,
            "window_504": res_504,
        })

    out_file = PROJECT_ROOT / "runs" / "lookback_comparison.json"
    out_file.parent.mkdir(exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(comparison_results, f, indent=2, default=str)

    logger.info("Saved lookback comparison to %s", out_file)
    print("\n--- LOOKBACK WINDOW COMPARISON SUMMARY ---")
    print(f"{'Pair':<26} | {'252d Corr':<9} | {'252d CointP':<11} | {'252d Status':<12} | {'504d Corr':<9} | {'504d CointP':<11} | {'504d Status':<12}")
    print("-" * 105)
    for row in comparison_results:
        w252 = row["window_252"]
        w504 = row["window_504"]
        c252 = f"{w252.get('pair_correlation', 0.0):.2f}" if w252.get('data_available') else "N/A"
        p252 = f"{w252.get('cointegration_pvalue', 1.0):.3f}" if w252.get('data_available') else "N/A"
        s252 = "APPROVED ✅" if w252.get('approved') else "REJECTED ❌"

        c504 = f"{w504.get('pair_correlation', 0.0):.2f}" if w504.get('data_available') else "N/A"
        p504 = f"{w504.get('cointegration_pvalue', 1.0):.3f}" if w504.get('data_available') else "N/A"
        s504 = "APPROVED ✅" if w504.get('approved') else "REJECTED ❌"

        print(f"{row['pair']:<26} | {c252:<9} | {p252:<11} | {s252:<12} | {c504:<9} | {p504:<11} | {s504:<12}")


if __name__ == "__main__":
    main()
