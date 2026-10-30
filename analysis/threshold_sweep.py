"""Threshold sweep across historical stress windows and pair universe.

Implements Task 4:
- Estimation / Test splits:
    gfc_2008:      estimate 2007-06-01 to 2007-12-31, test 2008-01-01 to 2008-12-31 (TRAIN)
    tech_2022:     estimate 2021-06-01 to 2021-12-31, test 2022-01-01 to 2022-06-30 (TRAIN)
    covid_2020:    estimate 2019-06-01 to 2020-01-31, test 2020-02-01 to 2020-04-30 (TEST)
    election_2024: estimate 2023-10-01 to 2024-05-15, test 2024-05-16 to 2024-06-30 (TEST)
- Evaluates all ordered pairs (A, B) across all sectors.
- Records all metrics and four gate pass/fail flags to analysis/results/sweep_results.csv.
- Computes and prints pass rates per sector and split.
- Identifies persistent pairs that passed all gates on both train windows and inspects test behavior.
"""

from __future__ import annotations

import itertools
import math
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

# Verification gate thresholds
GATE_MIN_CORR = 0.65
GATE_MAX_COINT_P = 0.05
GATE_MAX_MDD_RATIO = 0.50
GATE_MAX_REALIZED_BETA = 0.15

SECTORS = ["NIFTY_IT", "NIFTY_BANK", "NIFTY_AUTO", "NIFTY_PHARMA"]

WINDOWS = {
    "gfc_2008": {
        "split": "train",
        "est_start": "2007-06-01",
        "est_end": "2007-12-31",
        "test_start": "2008-01-01",
        "test_end": "2008-12-31",
    },
    "tech_2022": {
        "split": "train",
        "est_start": "2021-06-01",
        "est_end": "2021-12-31",
        "test_start": "2022-01-01",
        "test_end": "2022-06-30",
    },
    "covid_2020": {
        "split": "test",
        "est_start": "2019-06-01",
        "est_end": "2020-01-31",
        "test_start": "2020-02-01",
        "test_end": "2020-04-30",
    },
    "election_2024": {
        "split": "test",
        "est_start": "2023-10-01",
        "est_end": "2024-05-15",
        "test_start": "2024-05-16",
        "test_end": "2024-06-30",
    },
}


def compute_static_beta(stock_returns: pd.Series, market_returns: pd.Series) -> float:
    aligned = pd.concat({"stock": stock_returns, "market": market_returns}, axis=1).dropna()
    if len(aligned) < 2:
        return float("nan")
    cov_matrix = np.cov(aligned["stock"], aligned["market"])
    var_m = cov_matrix[1, 1]
    if var_m == 0.0 or np.isnan(var_m):
        return float("nan")
    return float(cov_matrix[0, 1] / var_m)


def compute_pair_correlation(long_returns: pd.Series, short_returns: pd.Series) -> float:
    aligned = pd.concat({"long": long_returns, "short": short_returns}, axis=1).dropna()
    if len(aligned) < 2:
        return float("nan")
    return float(np.corrcoef(aligned["long"], aligned["short"])[0, 1])


def compute_cointegration_pvalue(long_prices: pd.Series, short_prices: pd.Series) -> float:
    aligned = pd.concat({"long": long_prices, "short": short_prices}, axis=1).dropna()
    if len(aligned) < 15 or (aligned["long"] <= 0).any() or (aligned["short"] <= 0).any():
        return float("nan")
    try:
        _, p_val, _ = coint(np.log(aligned["long"]), np.log(aligned["short"]), trend="c")
        return float(p_val)
    except Exception:
        return float("nan")


def compute_ou_half_life(long_prices: pd.Series, short_prices: pd.Series) -> float:
    aligned = pd.concat({"long": long_prices, "short": short_prices}, axis=1).dropna()
    if len(aligned) < 5 or (aligned["long"] <= 0).any() or (aligned["short"] <= 0).any():
        return float("nan")
    spread = np.log(aligned["long"]) - np.log(aligned["short"])
    clean = spread.dropna()
    if len(clean) < 5:
        return float("nan")
    delta_s = clean.diff().iloc[1:]
    s_lag = clean.shift(1).iloc[1:]
    x = sm.add_constant(s_lag)
    try:
        model = sm.OLS(delta_s, x).fit()
        lam = float(model.params.iloc[1])
        if lam < 0.0:
            return float(-np.log(2.0) / lam)
        return float("inf")
    except Exception:
        return float("nan")


def run_sweep():
    os.makedirs("analysis/results", exist_ok=True)
    out_csv = "analysis/results/sweep_results.csv"

    results = []

    print("Running threshold sweep across 4 sectors x 4 stress regimes...")

    for sector in SECTORS:
        for win_name, win_cfg in WINDOWS.items():
            csv_path = f"scratch_data/{sector}__{win_name}.csv"
            if not os.path.exists(csv_path):
                csv_path = f"data_cache/{sector}__{win_name}.csv"
            if not os.path.exists(csv_path):
                print(f"Skipping {sector} {win_name}: file {csv_path} not found.")
                continue

            df = pd.read_csv(csv_path, parse_dates=["Date"]).set_index("Date")
            tickers = [c for c in df.columns if c not in ["Date", "^NSEI"]]
            benchmark = "^NSEI"

            est_start, est_end = win_cfg["est_start"], win_cfg["est_end"]
            test_start, test_end = win_cfg["test_start"], win_cfg["test_end"]
            split = win_cfg["split"]

            est_df = df.loc[est_start:est_end]
            test_df = df.loc[test_start:test_end]

            if len(est_df) < 15 or len(test_df) < 5:
                print(f"Skipping {sector} {win_name}: insufficient rows (est={len(est_df)}, test={len(test_df)})")
                continue

            # Compute estimation returns
            est_returns = est_df.pct_change().dropna()
            test_returns = test_df.pct_change().dropna()

            # Pairwise sweep
            for long_ticker, short_ticker in itertools.permutations(tickers, 2):
                if long_ticker not in est_returns.columns or short_ticker not in est_returns.columns:
                    continue

                r_l_est = est_returns[long_ticker]
                r_s_est = est_returns[short_ticker]
                r_m_est = est_returns[benchmark]

                p_l_est = est_df[long_ticker]
                p_s_est = est_df[short_ticker]

                # 1. Estimation metrics
                corr = compute_pair_correlation(r_l_est, r_s_est)
                coint_p = compute_cointegration_pvalue(p_l_est, p_s_est)
                ou_hl = compute_ou_half_life(p_l_est, p_s_est)

                beta_l_est = compute_static_beta(r_l_est, r_m_est)
                beta_s_est = compute_static_beta(r_s_est, r_m_est)

                if math.isnan(beta_l_est) or math.isnan(beta_s_est):
                    continue

                # Defensive handling of estimation betas for weights
                eff_bl = max(beta_l_est, 0.01)
                eff_bs = max(beta_s_est, 0.01)
                w_l = eff_bs / (eff_bl + eff_bs)
                w_s = -eff_bl / (eff_bl + eff_bs)

                # 2. Test metrics (out-of-sample)
                if long_ticker not in test_returns.columns or short_ticker not in test_returns.columns:
                    continue

                r_l_test = test_returns[long_ticker]
                r_s_test = test_returns[short_ticker]
                r_m_test = test_returns[benchmark]

                hedged_r = w_l * r_l_test + w_s * r_s_test
                unhedged_r = r_l_test

                # Cumulative return drawdowns
                cum_h = (1.0 + hedged_r).cumprod()
                running_max_h = cum_h.cummax()
                dd_h = (cum_h - running_max_h) / running_max_h
                mdd_hedged = abs(float(dd_h.min()))

                cum_u = (1.0 + unhedged_r).cumprod()
                running_max_u = cum_u.cummax()
                dd_u = (cum_u - running_max_u) / running_max_u
                mdd_unhedged = abs(float(dd_u.min()))

                if mdd_unhedged < 1e-4:
                    mdd_ratio = float("nan")
                else:
                    mdd_ratio = mdd_hedged / mdd_unhedged

                # Realized beta of hedged strategy vs market in test window
                realized_beta = compute_static_beta(hedged_r, r_m_test)

                # Annualized Sharpe (daily rf = 0.068 / 252)
                rf_daily = 0.068 / 252.0
                excess_r = hedged_r - rf_daily
                h_vol = float(hedged_r.std(ddof=1))
                if h_vol > 1e-8:
                    sharpe = float((excess_r.mean() / h_vol) * np.sqrt(252.0))
                else:
                    sharpe = 0.0

                # Sortino ratio using downside deviation
                downside_diff = np.minimum(0.0, excess_r)
                downside_dev = float(np.sqrt(np.mean(downside_diff ** 2)))
                if downside_dev > 1e-8:
                    sortino = float((excess_r.mean() / downside_dev) * np.sqrt(252.0))
                else:
                    sortino = 0.0

                var_95 = float(np.percentile(hedged_r, 5.0))

                # Verification Gates
                gate_corr = bool(not math.isnan(corr) and corr >= GATE_MIN_CORR)
                gate_coint = bool(not math.isnan(coint_p) and coint_p < GATE_MAX_COINT_P)
                gate_mdd = bool(not math.isnan(mdd_ratio) and mdd_ratio < GATE_MAX_MDD_RATIO)
                gate_beta = bool(not math.isnan(realized_beta) and abs(realized_beta) < GATE_MAX_REALIZED_BETA)

                all_gates = bool(gate_corr and gate_coint and gate_mdd and gate_beta)

                results.append({
                    "sector": sector,
                    "long": long_ticker,
                    "short": short_ticker,
                    "window": win_name,
                    "split": split,
                    "correlation": round(corr, 4) if not math.isnan(corr) else None,
                    "coint_pvalue": round(coint_p, 4) if not math.isnan(coint_p) else None,
                    "ou_half_life": round(ou_hl, 2) if (not math.isnan(ou_hl) and not math.isinf(ou_hl)) else ("inf" if math.isinf(ou_hl) else None),
                    "mdd_hedged": round(mdd_hedged, 4),
                    "mdd_unhedged": round(mdd_unhedged, 4),
                    "mdd_ratio": round(mdd_ratio, 4) if not math.isnan(mdd_ratio) else None,
                    "realized_beta": round(realized_beta, 4) if not math.isnan(realized_beta) else None,
                    "sharpe": round(sharpe, 4),
                    "sortino": round(sortino, 4),
                    "var_95": round(var_95, 4),
                    "gate_corr_pass": gate_corr,
                    "gate_coint_pass": gate_coint,
                    "gate_mdd_pass": gate_mdd,
                    "gate_beta_pass": gate_beta,
                    "all_gates_pass": all_gates,
                })

    df_res = pd.DataFrame(results)
    df_res.to_csv(out_csv, index=False)
    print(f"Sweep complete. Saved {len(df_res)} evaluated pair rows to {out_csv}.\n")

    # Aggregate summaries per sector and split
    print("=" * 80)
    print("PASS RATES PER SECTOR AND SPLIT (TRAIN vs TEST)")
    print("=" * 80)
    summary_rows = []
    for sector in SECTORS:
        for split in ["train", "test"]:
            sub = df_res[(df_res["sector"] == sector) & (df_res["split"] == split)]
            n = len(sub)
            if n == 0:
                continue
            p_corr = sub["gate_corr_pass"].mean() * 100.0
            p_coint = sub["gate_coint_pass"].mean() * 100.0
            p_mdd = sub["gate_mdd_pass"].mean() * 100.0
            p_beta = sub["gate_beta_pass"].mean() * 100.0
            p_all = sub["all_gates_pass"].mean() * 100.0
            summary_rows.append({
                "Sector": sector,
                "Split": split.upper(),
                "Pairs": n,
                "Corr Gate (>=0.65)": f"{p_corr:.1f}%",
                "Coint Gate (<0.05)": f"{p_coint:.1f}%",
                "MDD Gate (<0.50)": f"{p_mdd:.1f}%",
                "Beta Gate (<0.15)": f"{p_beta:.1f}%",
                "ALL 4 GATES": f"{p_all:.1f}%",
            })

    summary_df = pd.DataFrame(summary_rows)
    print(summary_df.to_string(index=False))

    # Identify pairs that pass on BOTH train windows
    print("\n" + "=" * 80)
    print("TOP CANDIDATE PAIRS PASSING ALL GATES ON BOTH TRAIN WINDOWS")
    print("(gfc_2008 AND tech_2022) -> Followed through to TEST Windows")
    print("=" * 80)

    for sector in SECTORS:
        print(f"\n--- Sector: {sector} ---")
        gfc = df_res[(df_res["sector"] == sector) & (df_res["window"] == "gfc_2008") & (df_res["all_gates_pass"])]
        tech = df_res[(df_res["sector"] == sector) & (df_res["window"] == "tech_2022") & (df_res["all_gates_pass"])]

        gfc_pairs = set(zip(gfc["long"], gfc["short"]))
        tech_pairs = set(zip(tech["long"], tech["short"]))
        both_train = gfc_pairs.intersection(tech_pairs)

        print(f"Pairs passing gfc_2008  : {len(gfc_pairs)}")
        print(f"Pairs passing tech_2022 : {len(tech_pairs)}")
        print(f"Pairs passing BOTH train: {len(both_train)}")

        if not both_train:
            print(f"No pairs in {sector} passed all 4 gates across both TRAIN windows.")
            # Check individual gate bottlenecks in train
            sec_train = df_res[(df_res["sector"] == sector) & (df_res["split"] == "train")]
            print("  Train gate pass rates: Corr={:.1f}%, Coint={:.1f}%, MDD={:.1f}%, Beta={:.1f}%".format(
                sec_train["gate_corr_pass"].mean() * 100,
                sec_train["gate_coint_pass"].mean() * 100,
                sec_train["gate_mdd_pass"].mean() * 100,
                sec_train["gate_beta_pass"].mean() * 100,
            ))
            # Also check test windows for any pairs passing both test windows
            covid_p = set(zip(
                df_res[(df_res["sector"] == sector) & (df_res["window"] == "covid_2020") & (df_res["all_gates_pass"])]["long"],
                df_res[(df_res["sector"] == sector) & (df_res["window"] == "covid_2020") & (df_res["all_gates_pass"])]["short"]
            ))
            elec_p = set(zip(
                df_res[(df_res["sector"] == sector) & (df_res["window"] == "election_2024") & (df_res["all_gates_pass"])]["long"],
                df_res[(df_res["sector"] == sector) & (df_res["window"] == "election_2024") & (df_res["all_gates_pass"])]["short"]
            ))
            both_test = covid_p.intersection(elec_p)
            print(f"  Pairs passing BOTH test windows (covid_2020 & election_2024): {len(both_test)}")
            for l, s in list(both_test)[:3]:
                print(f"    * Test-Approved Pair: Long={l}, Short={s}")
        else:
            for i, (l, s) in enumerate(list(both_train)[:5], 1):
                print(f"\n  Candidate {i}: Long={l}, Short={s}")
                for win in ["gfc_2008", "tech_2022", "covid_2020", "election_2024"]:
                    row = df_res[(df_res["sector"] == sector) & (df_res["window"] == win) & (df_res["long"] == l) & (df_res["short"] == s)]
                    if not row.empty:
                        r = row.iloc[0]
                        print(f"    [{win:<13}] Corr={r['correlation']}, CointP={r['coint_pvalue']}, MDD_ratio={r['mdd_ratio']}, Beta={r['realized_beta']}, Sharpe={r['sharpe']} -> ALL_PASS={r['all_gates_pass']}")
                    else:
                        print(f"    [{win:<13}] Data not available")


if __name__ == "__main__":
    run_sweep()
