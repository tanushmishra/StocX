"""Independent quantitative reference calculations for pair trading hedge analysis.

This module contains standalone quantitative implementations using ONLY numpy,
pandas, and statsmodels. It does NOT import anything from engine/ to serve as an
independent mathematical verification desk.
"""

from __future__ import annotations

import logging
import math
import sys
from typing import Any, Tuple

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.tsa.stattools import coint

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def compute_static_beta(
    stock_returns: pd.Series,
    market_returns: pd.Series,
) -> float:
    """Compute static OLS market beta: Cov(R_i, R_M) / Var(R_M)."""
    aligned = pd.concat({"stock": stock_returns, "market": market_returns}, axis=1).dropna()
    if len(aligned) < 2:
        raise ValueError("Insufficient data points to compute beta.")
    cov_matrix = np.cov(aligned["stock"], aligned["market"])
    var_m = cov_matrix[1, 1]
    if var_m == 0.0 or np.isnan(var_m):
        raise ValueError("Market variance is zero or NaN.")
    return float(cov_matrix[0, 1] / var_m)


def compute_pair_correlation(
    long_returns: pd.Series,
    short_returns: pd.Series,
) -> float:
    """Compute Pearson correlation coefficient between two return series."""
    aligned = pd.concat({"long": long_returns, "short": short_returns}, axis=1).dropna()
    if len(aligned) < 2:
        raise ValueError("Insufficient data points to compute correlation.")
    return float(np.corrcoef(aligned["long"], aligned["short"])[0, 1])


def compute_cointegration(
    long_prices: pd.Series,
    short_prices: pd.Series,
) -> Tuple[float, float, dict]:
    """Engle-Granger cointegration test on log prices (statsmodels.tsa.stattools.coint)."""
    aligned = pd.concat({"long": long_prices, "short": short_prices}, axis=1).dropna()
    if (aligned["long"] <= 0).any() or (aligned["short"] <= 0).any():
        raise ValueError("Prices must be strictly positive for log transform.")
    log_l = np.log(aligned["long"])
    log_s = np.log(aligned["short"])
    t_stat, p_val, crit_vals = coint(log_l, log_s, trend="c")
    crit_dict = {"1%": float(crit_vals[0]), "5%": float(crit_vals[1]), "10%": float(crit_vals[2])}
    return float(t_stat), float(p_val), crit_dict


def compute_ou_half_life(
    long_prices: pd.Series,
    short_prices: pd.Series,
) -> Tuple[float, float]:
    """Estimate Ornstein-Uhlenbeck half-life on log spread: ln(P_long) - ln(P_short).
    
    Regresses Delta(spread_t) on lagged spread (spread_{t-1}) with a constant:
    Delta S_t = alpha + lambda * S_{t-1} + eps_t.
    If lambda < 0: half_life = -ln(2) / lambda.
    If lambda >= 0: returns (lambda, float('inf')) as there is no mean reversion.
    """
    aligned = pd.concat({"long": long_prices, "short": short_prices}, axis=1).dropna()
    if (aligned["long"] <= 0).any() or (aligned["short"] <= 0).any():
        raise ValueError("Prices must be strictly positive for log transform.")
    spread = np.log(aligned["long"]) - np.log(aligned["short"])
    clean = spread.dropna()
    if len(clean) < 3:
        raise ValueError("Insufficient observations for OU regression.")
    
    delta_s = clean.diff().iloc[1:]
    s_lag = clean.shift(1).iloc[1:]
    
    x = sm.add_constant(s_lag)
    model = sm.OLS(delta_s, x).fit()
    lam = float(model.params.iloc[1])
    
    if lam < 0.0:
        half_life = float(-np.log(2.0) / lam)
    else:
        half_life = float("inf")
    return lam, half_life


def compute_beta_neutral_weights(
    beta_long: float,
    beta_short: float,
) -> Tuple[float, float, float, float]:
    """Analytic beta-neutral weights with gross exposure = 1.0.
    
    w_L = beta_S / (beta_L + beta_S)
    w_S = -beta_L / (beta_L + beta_S)
    Returns: (w_L, w_S, net_beta, gross_exposure)
    """
    denom = beta_long + beta_short
    if denom == 0.0:
        raise ValueError("Sum of betas is zero; cannot compute weights.")
    w_l = beta_short / denom
    w_s = -beta_long / denom
    net_beta = w_l * beta_long + w_s * beta_short
    gross_exposure = abs(w_l) + abs(w_s)
    return float(w_l), float(w_s), float(net_beta), float(gross_exposure)


def compute_ewma_beta_series(
    stock_returns: pd.Series,
    market_returns: pd.Series,
    decay: float = 0.94,
    span: int = 60,
) -> pd.Series:
    """EWMA beta following RiskMetrics recursive formulation with lambda = 0.94.
    
    sigma^2_{m,t} = lambda * sigma^2_{m,t-1} + (1 - lambda) * r_{m,t}^2
    sigma_{s,m,t} = lambda * sigma_{s,m,t-1} + (1 - lambda) * r_{s,t} * r_{m,t}
    beta_t = sigma_{s,m,t} / sigma^2_{m,t}
    """
    aligned = pd.concat({"stock": stock_returns, "market": market_returns}, axis=1).dropna()
    rs = aligned["stock"].values
    rm = aligned["market"].values
    n = len(rs)
    betas = np.full(n, np.nan)
    ewma_cov = np.full(n, np.nan)
    ewma_var = np.full(n, np.nan)
    
    seed_end = min(n, span)
    seed_cov = np.cov(rs[:seed_end], rm[:seed_end])
    ewma_cov[seed_end - 1] = seed_cov[0, 1]
    ewma_var[seed_end - 1] = seed_cov[1, 1]
    if ewma_var[seed_end - 1] != 0.0:
        betas[seed_end - 1] = ewma_cov[seed_end - 1] / ewma_var[seed_end - 1]
        
    for t in range(seed_end, n):
        ewma_var[t] = decay * ewma_var[t - 1] + (1 - decay) * (rm[t] ** 2)
        ewma_cov[t] = decay * ewma_cov[t - 1] + (1 - decay) * (rs[t] * rm[t])
        if ewma_var[t] != 0.0:
            betas[t] = ewma_cov[t] / ewma_var[t]
            
    return pd.Series(betas, index=aligned.index, name="ewma_beta")


def compute_rolling_beta_series(
    stock_returns: pd.Series,
    market_returns: pd.Series,
    window: int = 60,
) -> pd.Series:
    """60-day rolling OLS beta."""
    aligned = pd.concat({"stock": stock_returns, "market": market_returns}, axis=1).dropna()
    rolling_cov = aligned["stock"].rolling(window).cov(aligned["market"])
    rolling_var = aligned["market"].rolling(window).var(ddof=1)
    rolling_var = rolling_var.replace(0.0, np.nan)
    return (rolling_cov / rolling_var).rename("rolling_beta")


def check_sanity_warnings(
    beta_l: float,
    beta_s: float,
    corr: float,
    prefix: str = "",
) -> list[str]:
    """Check sanity ranges: beta in [0.3, 1.6], corr in [0.3, 0.95], no inf/NaN."""
    warnings = []
    for name, b in [("Long Beta", beta_l), ("Short Beta", beta_s)]:
        if math.isnan(b) or math.isinf(b):
            warnings.append(f"WARNING: {prefix}{name} is {b} (invalid numeric value)")
        elif not (0.3 <= b <= 1.6):
            warnings.append(f"WARNING: {prefix}{name} = {b:.4f} is outside normal bounds [0.3, 1.6]")
            
    if math.isnan(corr) or math.isinf(corr):
        warnings.append(f"WARNING: {prefix}Correlation is {corr} (invalid numeric value)")
    elif not (0.3 <= corr <= 0.95):
        warnings.append(f"WARNING: {prefix}Correlation = {corr:.4f} is outside typical pair bounds [0.3, 0.95]")
        
    return warnings


def crash_test(
    prices: pd.DataFrame,
    long_ticker: str,
    short_ticker: str,
    est_start: str,
    est_end: str,
    test_start: str,
    test_end: str,
    benchmark_ticker: str = "^NSEI",
    rf_annual: float = 0.068,
) -> dict[str, Any]:
    """Evaluate an out-of-sample crash backtest.
    
    1. Estimates betas and beta-neutral weights strictly on [est_start, est_end].
    2. Evaluates the constant-weight hedged strategy w_L * R_long + w_S * R_short and
       the unhedged long-only strategy on [test_start, test_end].
    3. Computes: MDD hedged, MDD unhedged, MDD ratio, realized beta, annualized Sharpe,
       annualized Sortino, and daily VaR95.
    """
    # Ensure datetime index
    df = prices.copy()
    if not isinstance(df.index, pd.DatetimeIndex):
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.set_index("Date")
        else:
            df.index = pd.to_datetime(df.index)
            
    # Estimation slice
    est_slice = df.loc[est_start:est_end, [long_ticker, short_ticker, benchmark_ticker]]
    est_returns = est_slice.pct_change().dropna()
    if len(est_returns) < 10:
        raise ValueError(f"Insufficient estimation data ({len(est_returns)} rows) between {est_start} and {est_end}.")
        
    beta_l = compute_static_beta(est_returns[long_ticker], est_returns[benchmark_ticker])
    beta_s = compute_static_beta(est_returns[short_ticker], est_returns[benchmark_ticker])
    
    # Handle non-positive estimation betas defensively
    eff_bl = max(beta_l, 0.01) if not (math.isnan(beta_l) or math.isinf(beta_l)) else 0.01
    eff_bs = max(beta_s, 0.01) if not (math.isnan(beta_s) or math.isinf(beta_s)) else 0.01
    w_l = eff_bs / (eff_bl + eff_bs)
    w_s = -eff_bl / (eff_bl + eff_bs)
    
    # Test slice
    test_slice = df.loc[test_start:test_end, [long_ticker, short_ticker, benchmark_ticker]]
    test_returns = test_slice.pct_change().dropna()
    if len(test_returns) < 5:
        raise ValueError(f"Insufficient test data ({len(test_returns)} rows) between {test_start} and {test_end}.")
        
    r_l = test_returns[long_ticker]
    r_s = test_returns[short_ticker]
    r_m = test_returns[benchmark_ticker]
    
    hedged_r = w_l * r_l + w_s * r_s
    unhedged_r = r_l
    
    # Max Drawdowns on cumulative curves
    cum_h = (1.0 + hedged_r).cumprod()
    running_max_h = cum_h.cummax()
    dd_h = (cum_h - running_max_h) / running_max_h
    mdd_hedged = abs(float(dd_h.min()))
    
    cum_u = (1.0 + unhedged_r).cumprod()
    running_max_u = cum_u.cummax()
    dd_u = (cum_u - running_max_u) / running_max_u
    mdd_unhedged = abs(float(dd_u.min()))
    
    # Guard against division by near-zero unhedged MDD
    if mdd_unhedged < 1e-4:
        mdd_ratio = float("nan")
    else:
        mdd_ratio = mdd_hedged / mdd_unhedged
        
    # Realized beta of hedged series vs market over test window
    try:
        realized_beta = compute_static_beta(hedged_r, r_m)
    except Exception:
        realized_beta = float("nan")
        
    # Annualized Sharpe (daily risk-free = 0.068 / 252, sqrt(252))
    rf_daily = rf_annual / 252.0
    excess_r = hedged_r - rf_daily
    h_vol = float(hedged_r.std(ddof=1))
    if h_vol > 1e-8:
        sharpe = float((excess_r.mean() / h_vol) * np.sqrt(252.0))
    else:
        sharpe = 0.0
        
    # Annualized Sortino using downside deviation
    downside_diff = np.minimum(0.0, excess_r)
    downside_dev = float(np.sqrt(np.mean(downside_diff ** 2)))
    if downside_dev > 1e-8:
        sortino = float((excess_r.mean() / downside_dev) * np.sqrt(252.0))
    else:
        sortino = 0.0
        
    # VaR95: 5th percentile of daily returns (historical left-tail)
    var_95 = float(np.percentile(hedged_r, 5.0))
    
    return {
        "est_beta_long": float(beta_l),
        "est_beta_short": float(beta_s),
        "w_long": float(w_l),
        "w_short": float(w_s),
        "mdd_hedged": mdd_hedged,
        "mdd_unhedged": mdd_unhedged,
        "mdd_ratio": mdd_ratio,
        "realized_beta": realized_beta,
        "sharpe": sharpe,
        "sortino": sortino,
        "var_95": var_95,
        "n_test_days": len(hedged_r),
    }


def main():
    print("=" * 80)
    print("TASK 2: INDEPENDENT REFERENCE CALCULATION (NO ENGINE IMPORTS)")
    print("=" * 80)
    
    csv_path = "scratch_data/NIFTY_IT__main_3y.csv"
    long_ticker = "TCS.NS"
    short_ticker = "WIPRO.NS"
    benchmark = "^NSEI"
    
    print(f"Loading reference dataset: {csv_path}")
    df = pd.read_csv(csv_path, parse_dates=["Date"]).set_index("Date")
    print(f"Data range: {df.index.min().date()} to {df.index.max().date()} ({len(df)} rows)")
    
    p_long = df[long_ticker]
    p_short = df[short_ticker]
    p_mkt = df[benchmark]
    
    returns = pd.concat({"long": p_long, "short": p_short, "market": p_mkt}, axis=1).pct_change().dropna()
    r_l = returns["long"]
    r_s = returns["short"]
    r_m = returns["market"]
    
    # 1. Betas
    b_l = compute_static_beta(r_l, r_m)
    b_s = compute_static_beta(r_s, r_m)
    
    # 2. Correlation
    corr = compute_pair_correlation(r_l, r_s)
    
    # 3. Cointegration on log prices
    coint_t, coint_p, coint_crit = compute_cointegration(p_long, p_short)
    
    # 4. OU Half-life
    ou_lam, ou_hl = compute_ou_half_life(p_long, p_short)
    
    # 5. Beta-neutral weights
    w_l, w_s, net_beta, gross = compute_beta_neutral_weights(b_l, b_s)
    
    # 6. EWMA and Rolling Betas
    ewma_l = compute_ewma_beta_series(r_l, r_m).dropna().iloc[-1]
    ewma_s = compute_ewma_beta_series(r_s, r_m).dropna().iloc[-1]
    roll_l = compute_rolling_beta_series(r_l, r_m, window=60).dropna().iloc[-1]
    roll_s = compute_rolling_beta_series(r_s, r_m, window=60).dropna().iloc[-1]
    
    # Sanity checks
    warnings = check_sanity_warnings(b_l, b_s, corr)
    
    print("\n--- Summary Reference Metrics: TCS.NS (Long) vs WIPRO.NS (Short) ---")
    print(f"Static Beta Long (TCS.NS)   : {b_l:.6f}")
    print(f"Static Beta Short (WIPRO.NS): {b_s:.6f}")
    print(f"Pair Return Correlation     : {corr:.6f}")
    print(f"Engle-Granger Cointegration : t-stat = {coint_t:.6f}, p-value = {coint_p:.6f}")
    print(f"  Critical Values           : {coint_crit}")
    print(f"OU Mean Reversion Parameter : lambda = {ou_lam:.6f}")
    print(f"OU Half-Life (days)         : {ou_hl:.6f}")
    print(f"Beta-Neutral Weights        : w_Long = {w_l:.6f}, w_Short = {w_s:.6f}")
    print(f"Net Portfolio Beta          : {net_beta:.6e}")
    print(f"Gross Capital Leverage      : {gross:.6f}")
    print(f"EWMA Beta (latest, lambda=0.94): Long = {ewma_l:.6f}, Short = {ewma_s:.6f}")
    print(f"60-day Rolling Beta (latest): Long = {roll_l:.6f}, Short = {roll_s:.6f}")
    
    if warnings:
        print("\nSANITY WARNINGS:")
        for w in warnings:
            print(f"  {w}")
    else:
        print("\nSANITY CHECK: All metrics within expected theoretical ranges.")
        
    print("\n" + "=" * 80)
    print("CRASH TEST REFERENCE ON COVID_2020 WINDOW")
    print("Estimation: 2019-06-01 to 2020-01-31 | Test: 2020-02-01 to 2020-04-30")
    print("=" * 80)
    covid_df = pd.read_csv("scratch_data/NIFTY_IT__covid_2020.csv", parse_dates=["Date"]).set_index("Date")
    ct_res = crash_test(
        prices=covid_df,
        long_ticker="TCS.NS",
        short_ticker="WIPRO.NS",
        est_start="2019-06-01",
        est_end="2020-01-31",
        test_start="2020-02-01",
        test_end="2020-04-30",
    )
    for k, v in ct_res.items():
        if isinstance(v, float):
            print(f"{k:20s}: {v:12.6f}")
        else:
            print(f"{k:20s}: {v}")


if __name__ == "__main__":
    main()
