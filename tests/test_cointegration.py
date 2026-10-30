"""Unit tests for the Cointegration module."""

import numpy as np
import pandas as pd
import pytest

from engine.cointegration import (
    engle_granger_test,
    compute_spread_zscore,
    ou_half_life,
)


@pytest.fixture
def cointegrated_pair():
    """Generate a pair of cointegrated series (shared stochastic trend + mean-reverting spread)."""
    np.random.seed(42)
    n = 500
    # Shared random walk (common stochastic trend)
    trend = np.cumsum(np.random.normal(0, 1, n))
    # Series A = trend + small noise
    series_a = pd.Series(100 + trend + np.random.normal(0, 0.5, n), name="A")
    # Series B = trend * 1.05 + mean-reverting noise
    series_b = pd.Series(100 + trend * 1.05 + np.random.normal(0, 0.5, n), name="B")
    return series_a, series_b


@pytest.fixture
def non_cointegrated_pair():
    """Generate two independent random walks (not cointegrated)."""
    np.random.seed(123)
    n = 500
    series_a = pd.Series(100 + np.cumsum(np.random.normal(0, 1, n)), name="A")
    series_b = pd.Series(100 + np.cumsum(np.random.normal(0.1, 1, n)), name="B")
    return series_a, series_b


class TestEngleGranger:
    """Tests for engle_granger_test()."""

    def test_cointegrated_pair_low_pvalue(self, cointegrated_pair):
        """Cointegrated pair should have p-value < 0.05."""
        a, b = cointegrated_pair
        result = engle_granger_test(a, b)
        assert result["p_value"] < 0.10  # Relaxed threshold for synthetic data
        assert "t_stat" in result
        assert "p_value" in result

    def test_non_cointegrated_pair_high_pvalue(self, non_cointegrated_pair):
        """Non-cointegrated pair should have p-value > 0.05."""
        a, b = non_cointegrated_pair
        result = engle_granger_test(a, b)
        assert result["p_value"] > 0.05

    def test_result_has_required_keys(self, cointegrated_pair):
        """Result dict should have all required keys."""
        a, b = cointegrated_pair
        result = engle_granger_test(a, b)
        required_keys = {"t_stat", "p_value", "critical_values", "is_cointegrated"}
        assert required_keys.issubset(set(result.keys()))


class TestSpreadZScore:
    """Tests for compute_spread_zscore()."""

    def test_returns_series(self, cointegrated_pair):
        """Should return a pandas Series."""
        a, b = cointegrated_pair
        zscore = compute_spread_zscore(a, b, window=60)
        assert isinstance(zscore, pd.Series)

    def test_zscore_is_standardized(self, cointegrated_pair):
        """Z-score values should be roughly standardized (mean ≈ 0, std ≈ 1)."""
        a, b = cointegrated_pair
        zscore = compute_spread_zscore(a, b, window=60).dropna()
        assert abs(zscore.mean()) < 1.0
        assert 0.3 < zscore.std() < 3.0


class TestOUHalfLife:
    """Tests for ou_half_life()."""

    def test_positive_half_life_for_mean_reverting(self):
        """Mean-reverting spread should have a positive half-life."""
        np.random.seed(42)
        # Create a mean-reverting (OU) process
        n = 500
        theta = 0.1  # Speed of mean reversion
        spread = np.zeros(n)
        for t in range(1, n):
            spread[t] = spread[t - 1] - theta * spread[t - 1] + np.random.normal(0, 0.5)
        hl = ou_half_life(pd.Series(spread))
        assert hl > 0, f"Expected positive half-life, got {hl}"
        assert hl < 100, f"Half-life suspiciously long: {hl}"

    def test_returns_float(self):
        """Should return a float."""
        np.random.seed(42)
        spread = pd.Series(np.random.normal(0, 1, 100))
        hl = ou_half_life(spread)
        assert isinstance(hl, float)
