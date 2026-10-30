"""Showcase analysis script to extract top pairs and run exploratory 2-year cointegration."""

import os
import sys

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import coint
import yfinance as yf

# Load sweep results
df = pd.read_csv("analysis/results/sweep_results.csv")
df["gates_passed_count"] = (
    df["gate_corr_pass"].astype(int)
    + df["gate_coint_pass"].astype(int)
    + df["gate_mdd_pass"].astype(int)
    + df["gate_beta_pass"].astype(int)
)

test_df = df[df["split"] == "test"]
sectors = ["NIFTY_IT", "NIFTY_BANK", "NIFTY_AUTO", "NIFTY_PHARMA"]

top_pairs_by_sector = {}

print("=" * 80)
print("TOP 5 TEST PAIRS PER SECTOR (RANKED BY GATES PASSED, MDD RATIO, SHARPE)")
print("=" * 80)

for sector in sectors:
    print(f"\n### Sector: {sector}")
    sub = test_df[test_df["sector"] == sector].sort_values(
        by=["gates_passed_count", "mdd_ratio", "sharpe"],
        ascending=[False, True, False],
    ).head(5)

    top_pairs_by_sector[sector] = sub

    for _, r in sub.iterrows():
        failed = []
        if not r["gate_corr_pass"]:
            failed.append("Correlation (>= 0.65)")
        if not r["gate_coint_pass"]:
            failed.append("Cointegration (p < 0.05)")
        if not r["gate_mdd_pass"]:
            failed.append("MDD Ratio (< 0.50)")
        if not r["gate_beta_pass"]:
            failed.append("|Realized Beta| (< 0.15)")

        fail_str = ", ".join(failed) if failed else "None (All 4 Passed)"
        print(
            f"* {r['long']} / {r['short']} ({r['window']}): "
            f"Gates Passed: {r['gates_passed_count']}/4 | "
            f"Corr: {r['correlation']:.4f} | "
            f"Coint p: {r['coint_pvalue']:.4f} | "
            f"MDD Ratio: {r['mdd_ratio']:.4f} (Hedged: {r['mdd_hedged']:.4f}, Unhedged: {r['mdd_unhedged']:.4f}) | "
            f"Beta: {r['realized_beta']:.4f} | "
            f"Failed: {fail_str}"
        )

# Rejection example details
print("\n" + "=" * 80)
print("REJECTION EXAMPLE: HDFCBANK / KOTAKBANK in COVID_2020")
print("=" * 80)
rej = test_df[
    (test_df["sector"] == "NIFTY_BANK")
    & (test_df["window"] == "covid_2020")
    & (test_df["long"] == "HDFCBANK.NS")
    & (test_df["short"] == "KOTAKBANK.NS")
].iloc[0]

print(f"Long: {rej['long']}, Short: {rej['short']}, Window: {rej['window']}")
print(f"Gates Passed: {rej['gates_passed_count']}/4")
print(f"Correlation: {rej['correlation']:.4f} (Pass >= 0.65)")
print(f"Cointegration p-value: {rej['coint_pvalue']:.4f} (FAIL < 0.05)")
print(f"MDD Ratio: {rej['mdd_ratio']:.4f} (Pass < 0.50) [Hedged: {rej['mdd_hedged']:.4f}, Unhedged: {rej['mdd_unhedged']:.4f}]")
print(f"Realized Beta: {rej['realized_beta']:.4f} (Pass < 0.15)")
print(f"OU Half-life: {rej['ou_half_life']} days, Sharpe: {rej['sharpe']:.4f}")
