"""Quantitative regression and mathematical invariant tests.

Validates:
(a) Analytic property tests for beta-neutral weights (net beta = 0, gross leverage = 1,
    and invalid beta edge cases).
(b) OU half-life non-mean-reversion tests ensuring non-reverting series return infinity/no-reversion
    rather than spurious finite numbers.
(c) Reference vs Engine comparison on real market data (skipped gracefully if file absent).
"""

from __future__ import annotations

import math
import os
import numpy as np
import pandas as pd
import pytest

from engine.portfolio import compute_beta_neutral_weights
from engine.cointegration import ou_half_life, engle_granger_test
from engine.beta_calculator import compute_static_beta
from engine.backtester import calc_metrics


class TestBetaNeutralWeightsProperties:
    """Property tests for beta-neutral position sizing formulas."""

    @pytest.mark.parametrize(
        "beta_long, beta_short",
        [
            (1.0, 1.0),
            (0.8, 1.2),
            (1.5, 0.5),
            (0.3, 1.7),
            (0.4, 2.6),
            (1.85, 0.95),
            (0.05, 0.95),
        ],
    )
    def test_net_beta_is_zero(self, beta_long: float, beta_short: float):
        """Net portfolio beta (w_L * beta_L + w_S * beta_S) must be 0."""
        w = compute_beta_neutral_weights(beta_long, beta_short)
        net_beta = w["w_long"] * beta_long + w["w_short"] * beta_short
        assert abs(net_beta) < 1e-12, f"Net beta non-zero ({net_beta}) for betas ({beta_long}, {beta_short})"

    @pytest.mark.parametrize(
        "beta_long, beta_short",
        [
            (1.0, 1.0),
            (0.8, 1.2),
            (1.5, 0.5),
            (0.2, 1.8),
            (0.4, 2.5),
        ],
    )
    def test_gross_leverage_is_one(self, beta_long: float, beta_short: float):
        """Gross exposure |w_L| + |w_S| must strictly equal 1.0."""
        w = compute_beta_neutral_weights(beta_long, beta_short)
        gross_leverage = abs(w["w_long"]) + abs(w["w_short"])
        assert abs(gross_leverage - 1.0) < 1e-12

    def test_invalid_zero_denominator_raises_value_error(self):
        """When beta_long + beta_short == 0 (or non-positive), must raise ValueError."""
        with pytest.raises(ValueError, match="must be > 0|Sum of betas is zero"):
            compute_beta_neutral_weights(0.0, 0.0)

        with pytest.raises(ValueError):
            compute_beta_neutral_weights(-1.0, 1.0)

        with pytest.raises(ValueError):
            compute_beta_neutral_weights(1.0, -1.0)


class TestOUHalfLifeNonMeanReverting:
    """Tests for OU half-life on non-mean-reverting and explosive series."""

    def test_trending_series_returns_infinity(self):
        """A strictly trending series (theta >= 0) must return infinity/no mean reversion."""
        # Strictly upward linear trend -> diff is constant, lagged spread increases -> theta >= 0
        trend = pd.Series(np.arange(1, 101, dtype=float))
        hl = ou_half_life(trend)
        # Must report infinity (no mean reversion) and NOT a finite number
        assert math.isinf(hl), f"Expected inf for trending series, got {hl}"
        assert not (math.isfinite(hl) and hl > 0), "Should not return a finite positive half-life"

    def test_pure_random_walk_drift_returns_infinity(self):
        """An explosive series must return infinity indicating no mean reversion."""
        np.random.seed(42)
        # Explosive series S_t = 1.05 * S_{t-1} + eps -> diff is positive and growing
        n = 100
        explosive = [10.0]
        for _ in range(n - 1):
            explosive.append(explosive[-1] * 1.02 + np.random.normal(0, 0.1))
        hl = ou_half_life(pd.Series(explosive))
        assert math.isinf(hl) or hl is None, f"Expected inf/None for explosive series, got {hl}"

    def test_stationary_series_returns_finite_positive_half_life(self):
        """A true stationary AR(1) series must return a valid positive half-life."""
        np.random.seed(42)
        n = 500
        spread = np.zeros(n)
        for t in range(1, n):
            spread[t] = 0.8 * spread[t - 1] + np.random.normal(0, 0.5)
        hl = ou_half_life(pd.Series(spread))
        assert math.isfinite(hl) and hl > 0, f"Expected finite positive half-life, got {hl}"


class TestRiskMetricsMath:
    """Verifies that calc_metrics adheres to institutional quant formulas."""

    def test_simple_daily_risk_free_rate(self):
        """calc_metrics must use simple annualization rf / 252."""
        returns = pd.Series([0.001, 0.002, -0.001, 0.0005, 0.0015] * 50)
        mkt = pd.Series([0.0008, 0.0015, -0.0008, 0.0004, 0.0012] * 50)
        m = calc_metrics(returns, mkt, rf_rate=0.068)
        
        # Manually compute with simple daily rf
        rf_daily = 0.068 / 252.0
        excess = returns - rf_daily
        vol = returns.std(ddof=1) * np.sqrt(252.0)
        expected_sharpe = round(float(excess.mean() / returns.std(ddof=1) * np.sqrt(252.0)), 4)
        assert abs(m["sharpe_ratio"] - expected_sharpe) < 1e-4


class TestRealDataReferenceVsEngine:
    """Compares independent reference math vs quant engine on real market data."""

    def test_real_nifty_it_reference_vs_engine_match(self):
        """Verify engine matches reference calculations within 1e-4 tolerance."""
        csv_path = "scratch_data/NIFTY_IT__main_3y.csv"
        if not os.path.exists(csv_path):
            csv_path = "data_cache/NIFTY_IT__main_3y.csv"
        if not os.path.exists(csv_path):
            pytest.skip("Real CSV NIFTY_IT__main_3y.csv not found; skipping integration test.")

        df = pd.read_csv(csv_path, parse_dates=["Date"]).set_index("Date")
        if "TCS.NS" not in df.columns or "WIPRO.NS" not in df.columns or "^NSEI" not in df.columns:
            pytest.skip("Required tickers missing from CSV; skipping.")

        p_l = df["TCS.NS"]
        p_s = df["WIPRO.NS"]
        p_m = df["^NSEI"]

        rets = pd.concat({"l": p_l, "s": p_s, "m": p_m}, axis=1).pct_change().dropna()
        
        # Engine calls
        eng_b_l = compute_static_beta(rets["l"], rets["m"])
        eng_b_s = compute_static_beta(rets["s"], rets["m"])
        eng_w = compute_beta_neutral_weights(eng_b_l, eng_b_s)
        eng_hl = ou_half_life(np.log(p_l) - np.log(p_s))
        eng_coint = engle_granger_test(np.log(p_l), np.log(p_s))

        # Analytic reference values
        cov_l = np.cov(rets["l"], rets["m"])
        ref_b_l = cov_l[0, 1] / cov_l[1, 1]
        cov_s = np.cov(rets["s"], rets["m"])
        ref_b_s = cov_s[0, 1] / cov_s[1, 1]
        ref_wl = ref_b_s / (ref_b_l + ref_b_s)
        ref_ws = -ref_b_l / (ref_b_l + ref_b_s)

        assert abs(eng_b_l - ref_b_l) < 1e-4
        assert abs(eng_b_s - ref_b_s) < 1e-4
        assert abs(eng_w["w_long"] - ref_wl) < 1e-4
        assert abs(eng_w["w_short"] - ref_ws) < 1e-4
        assert eng_coint["is_cointegrated"] is False
        assert 50 < eng_hl < 150  # Around ~94.4 days
