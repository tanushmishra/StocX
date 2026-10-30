"""Comparison script between independent reference and engine implementations."""

import sys
import os
sys.path.insert(0, os.path.abspath("."))
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

import pandas as pd
import numpy as np

from analysis.quant_check import (
    compute_static_beta as ref_static_beta,
    compute_pair_correlation as ref_pair_corr,
    compute_cointegration as ref_coint,
    compute_ou_half_life as ref_ou_hl,
    compute_beta_neutral_weights as ref_weights,
    compute_ewma_beta_series as ref_ewma,
    compute_rolling_beta_series as ref_rolling,
    crash_test as ref_crash_test,
)
from engine.beta_calculator import (
    compute_static_beta as eng_static_beta,
    compute_ewma_beta as eng_ewma_beta,
    compute_rolling_beta as eng_rolling_beta,
)
from engine.cointegration import engle_granger_test as eng_coint, ou_half_life as eng_ou_hl
from engine.portfolio import compute_beta_neutral_weights as eng_weights
from engine.backtester import backtest_pair, calc_metrics

def main():
    # Load main_3y
    df_main = pd.read_csv("scratch_data/NIFTY_IT__main_3y.csv", parse_dates=["Date"]).set_index("Date")
    p_l = df_main["TCS.NS"]
    p_s = df_main["WIPRO.NS"]
    p_m = df_main["^NSEI"]

    rets = pd.concat({"l": p_l, "s": p_s, "m": p_m}, axis=1).pct_change().dropna()

    # 1. Betas
    r_b_l = ref_static_beta(rets["l"], rets["m"])
    e_b_l = eng_static_beta(rets["l"], rets["m"])

    r_b_s = ref_static_beta(rets["s"], rets["m"])
    e_b_s = eng_static_beta(rets["s"], rets["m"])

    # 2. Correlation
    r_corr = ref_pair_corr(rets["l"], rets["s"])
    e_corr = float(rets["l"].corr(rets["s"]))

    # 3. Weights
    r_wl, r_ws, r_nb, r_gross = ref_weights(r_b_l, r_b_s)
    e_w_dict = eng_weights(e_b_l, e_b_s)
    e_wl = e_w_dict["w_long"]
    e_ws = e_w_dict["w_short"]

    # 4. OU half-life
    _, r_hl = ref_ou_hl(p_l, p_s)
    e_hl = eng_ou_hl(np.log(p_l) - np.log(p_s))

    # 5. EWMA beta (latest)
    r_ewma_l = ref_ewma(rets["l"], rets["m"]).dropna().iloc[-1]
    e_ewma_l = float(eng_ewma_beta(rets["l"], rets["m"]).dropna().iloc[-1])

    r_ewma_s = ref_ewma(rets["s"], rets["m"]).dropna().iloc[-1]
    e_ewma_s = float(eng_ewma_beta(rets["s"], rets["m"]).dropna().iloc[-1])

    # 6. Rolling beta 60d (latest)
    r_roll_l = ref_rolling(rets["l"], rets["m"], window=60).dropna().iloc[-1]
    e_roll_l = float(eng_rolling_beta(rets["l"], rets["m"], window=60).dropna().iloc[-1])

    r_roll_s = ref_rolling(rets["s"], rets["m"], window=60).dropna().iloc[-1]
    e_roll_s = float(eng_rolling_beta(rets["s"], rets["m"], window=60).dropna().iloc[-1])

    # 7. Cointegration
    r_coint_t, r_coint_p, _ = ref_coint(p_l, p_s)
    e_coint_raw = eng_coint(p_l, p_s) # engine called with raw prices
    e_coint_log = eng_coint(np.log(p_l), np.log(p_s)) # engine called with log prices

    # 8. COVID Crash Test
    df_covid = pd.read_csv("scratch_data/NIFTY_IT__covid_2020.csv", parse_dates=["Date"]).set_index("Date")
    r_crash = ref_crash_test(df_covid, "TCS.NS", "WIPRO.NS", "2019-06-01", "2020-01-31", "2020-02-01", "2020-04-30")

    # Engine backtest on covid test window
    test_slice = df_covid.loc["2020-02-01":"2020-04-30", ["TCS.NS", "WIPRO.NS", "^NSEI"]].pct_change().dropna()
    e_bt = backtest_pair(test_slice["TCS.NS"], test_slice["WIPRO.NS"], test_slice["^NSEI"], r_crash["w_long"], r_crash["w_short"])
    e_hm = e_bt["hedged_metrics"]
    e_um = e_bt["unhedged_metrics"]

    print("=== MAIN_3Y & COVID_2020 METRICS COMPARISON ===")
    rows = [
        ("Beta Long (TCS.NS)", r_b_l, e_b_l, 1e-4),
        ("Beta Short (WIPRO.NS)", r_b_s, e_b_s, 1e-4),
        ("Pair Correlation", r_corr, e_corr, 1e-4),
        ("Weight Long (w_L)", r_wl, e_wl, 1e-4),
        ("Weight Short (w_S)", r_ws, e_ws, 1e-4),
        ("OU Half-Life (days)", r_hl, e_hl, 1e-4),
        ("EWMA Beta Long", r_ewma_l, e_ewma_l, 1e-4),
        ("EWMA Beta Short", r_ewma_s, e_ewma_s, 1e-4),
        ("Rolling 60d Beta Long", r_roll_l, e_roll_l, 1e-4),
        ("Rolling 60d Beta Short", r_roll_s, e_roll_s, 1e-4),
        ("Coint p-value (engine on log)", r_coint_p, e_coint_log["p_value"], 1e-4),
        ("Coint p-value (engine on raw)", r_coint_p, e_coint_raw["p_value"], 1e-4),
        ("Crash Hedged MDD", r_crash["mdd_hedged"], abs(e_hm["max_drawdown"]), 1e-4),
        ("Crash Unhedged MDD", r_crash["mdd_unhedged"], abs(e_um["max_drawdown"]), 1e-4),
        ("Crash MDD Ratio", r_crash["mdd_ratio"], abs(e_hm["max_drawdown"]) / abs(e_um["max_drawdown"]), 1e-4),
        ("Crash Realized Beta", r_crash["realized_beta"], e_hm["realized_beta"], 1e-4),
        ("Crash Sharpe Ratio", r_crash["sharpe"], e_hm["sharpe_ratio"], 1e-4),
        ("Crash Sortino Ratio", r_crash["sortino"], e_hm["sortino_ratio"], 1e-4),
        ("Crash VaR 95%", r_crash["var_95"], e_hm["var_95"], 1e-4),
    ]

    header = f"{'Metric':<30} | {'Reference':<12} | {'Engine':<12} | {'Abs Diff':<10} | {'Status'}"
    print(header)
    print("-" * len(header))
    for name, ref_v, eng_v, tol in rows:
        diff = abs(ref_v - eng_v)
        status = "MATCH" if diff <= tol else "MISMATCH"
        print(f"{name:<30} | {ref_v:<12.6f} | {eng_v:<12.6f} | {diff:<10.6f} | {status}")

if __name__ == "__main__":
    main()
