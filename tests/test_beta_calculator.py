"""Unit tests for the Beta Calculator module."""

import numpy as np
import pandas as pd
import pytest

from engine.beta_calculator import (
    compute_static_beta,
    compute_ewma_beta,
    compute_rolling_beta,
)


@pytest.fixture
def sample_returns():
    """Generate deterministic sample return series for testing."""
    np.random.seed(42)
    n = 252  # One trading year
    market = pd.Series(np.random.normal(0.0005, 0.015, n), name="market")
    # Stock with beta ≈ 1.2 (amplifies market moves)
    stock_high_beta = market * 1.2 + pd.Series(
        np.random.normal(0, 0.005, n), name="noise"
    )
    stock_high_beta.name = "high_beta"
    # Stock with beta ≈ 0.8 (dampens market moves)
    stock_low_beta = market * 0.8 + pd.Series(
        np.random.normal(0, 0.005, n), name="noise"
    )
    stock_low_beta.name = "low_beta"
    return market, stock_high_beta, stock_low_beta


class TestStaticBeta:
    """Tests for compute_static_beta()."""

    def test_beta_of_market_against_itself_is_one(self, sample_returns):
        """Beta of the market against itself should be exactly 1.0."""
        market, _, _ = sample_returns
        beta = compute_static_beta(market, market)
        assert abs(beta - 1.0) < 1e-10

    def test_high_beta_stock_above_one(self, sample_returns):
        """A stock constructed with beta ≈ 1.2 should compute beta > 1.0."""
        market, high_beta, _ = sample_returns
        beta = compute_static_beta(high_beta, market)
        assert beta > 1.0, f"Expected beta > 1.0, got {beta}"

    def test_low_beta_stock_below_one(self, sample_returns):
        """A stock constructed with beta ≈ 0.8 should compute beta < 1.0."""
        market, _, low_beta = sample_returns
        beta = compute_static_beta(low_beta, market)
        assert beta < 1.0, f"Expected beta < 1.0, got {beta}"

    def test_beta_returns_float(self, sample_returns):
        """Beta should always return a float."""
        market, high_beta, _ = sample_returns
        beta = compute_static_beta(high_beta, market)
        assert isinstance(beta, float)

    def test_zero_variance_market_raises_or_returns_nan(self):
        """If market has zero variance, beta should handle gracefully."""
        flat_market = pd.Series([0.0] * 100)
        stock = pd.Series(np.random.normal(0, 0.01, 100))
        # Should either raise ValueError or return NaN/inf
        try:
            beta = compute_static_beta(stock, flat_market)
            assert np.isnan(beta) or np.isinf(beta)
        except (ValueError, ZeroDivisionError):
            pass  # Also acceptable


class TestEWMABeta:
    """Tests for compute_ewma_beta()."""

    def test_returns_series(self, sample_returns):
        """EWMA beta should return a pandas Series."""
        market, high_beta, _ = sample_returns
        result = compute_ewma_beta(high_beta, market)
        assert isinstance(result, pd.Series)

    def test_series_length_matches_input(self, sample_returns):
        """Output series length should match input length."""
        market, high_beta, _ = sample_returns
        result = compute_ewma_beta(high_beta, market)
        assert len(result) == len(high_beta)

    def test_ewma_beta_converges(self, sample_returns):
        """EWMA beta should converge to approximately the true beta."""
        market, high_beta, _ = sample_returns
        result = compute_ewma_beta(high_beta, market, span=60)
        # Last value should be close to the static beta
        static_beta = compute_static_beta(high_beta, market)
        assert abs(result.iloc[-1] - static_beta) < 0.5


class TestRollingBeta:
    """Tests for compute_rolling_beta()."""

    def test_returns_series(self, sample_returns):
        """Rolling beta should return a pandas Series."""
        market, high_beta, _ = sample_returns
        result = compute_rolling_beta(high_beta, market, window=60)
        assert isinstance(result, pd.Series)

    def test_initial_nans(self, sample_returns):
        """First (window-1) values should be NaN."""
        market, high_beta, _ = sample_returns
        window = 60
        result = compute_rolling_beta(high_beta, market, window=window)
        assert result.iloc[: window - 1].isna().all()

    def test_rolling_beta_values_reasonable(self, sample_returns):
        """Rolling beta values should be in a reasonable range."""
        market, high_beta, _ = sample_returns
        result = compute_rolling_beta(high_beta, market, window=60)
        valid = result.dropna()
        assert valid.min() > -5.0
        assert valid.max() < 5.0
