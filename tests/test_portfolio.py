"""Unit tests for the Portfolio module."""

import numpy as np
import pytest

from engine.portfolio import compute_beta_neutral_weights


class TestBetaNeutralWeights:
    """Tests for compute_beta_neutral_weights()."""

    def test_standard_case(self):
        """Standard case: beta_L=0.8, beta_S=1.2 → w_L=+0.6, w_S=-0.4."""
        result = compute_beta_neutral_weights(beta_long=0.8, beta_short=1.2)
        assert abs(result["long"] - 0.6) < 1e-10
        assert abs(result["short"] - (-0.4)) < 1e-10

    def test_portfolio_beta_is_zero(self):
        """Net portfolio beta should be exactly zero."""
        for bl, bs in [(0.8, 1.2), (1.0, 1.0), (0.5, 1.5), (1.3, 0.7)]:
            w = compute_beta_neutral_weights(bl, bs)
            portfolio_beta = w["long"] * bl + w["short"] * bs
            assert abs(portfolio_beta) < 1e-10, (
                f"Portfolio beta = {portfolio_beta} for betas ({bl}, {bs})"
            )

    def test_weights_sum_to_one_gross(self):
        """Gross exposure |w_L| + |w_S| should equal 1.0."""
        for bl, bs in [(0.8, 1.2), (1.0, 1.0), (0.5, 1.5)]:
            w = compute_beta_neutral_weights(bl, bs)
            gross = abs(w["long"]) + abs(w["short"])
            assert abs(gross - 1.0) < 1e-10

    def test_equal_betas_gives_equal_weights(self):
        """Equal betas should give 50/50 weights."""
        w = compute_beta_neutral_weights(1.0, 1.0)
        assert abs(w["long"] - 0.5) < 1e-10
        assert abs(w["short"] - (-0.5)) < 1e-10

    def test_long_weight_is_positive(self):
        """Long weight should always be positive."""
        w = compute_beta_neutral_weights(0.8, 1.2)
        assert w["long"] > 0

    def test_short_weight_is_negative(self):
        """Short weight should always be negative."""
        w = compute_beta_neutral_weights(0.8, 1.2)
        assert w["short"] < 0
