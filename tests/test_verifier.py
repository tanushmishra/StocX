"""Unit tests for the Verifier module."""

import pytest

from engine.verifier import verify_pair


class TestVerifyPair:
    """Tests for verify_pair() guardrail checks."""

    @pytest.fixture
    def passing_metrics(self):
        """Metrics that should pass all guardrails."""
        return {
            "pair_metrics": {
                "correlation": 0.85,
                "cointegration_pvalue": 0.01,
            },
            "unhedged_stats": {
                "max_drawdown_pct": -30.0,
                "realized_beta": 1.1,
            },
            "hedged_stats": {
                "max_drawdown_pct": -8.0,
                "realized_beta": 0.05,
            },
        }

    @pytest.fixture
    def failing_correlation(self):
        """Metrics with correlation below threshold."""
        return {
            "pair_metrics": {
                "correlation": 0.40,  # Below 0.65
                "cointegration_pvalue": 0.01,
            },
            "unhedged_stats": {
                "max_drawdown_pct": -30.0,
                "realized_beta": 1.1,
            },
            "hedged_stats": {
                "max_drawdown_pct": -8.0,
                "realized_beta": 0.05,
            },
        }

    def test_passing_pair_approved(self, passing_metrics):
        """A pair meeting all guardrails should be approved."""
        result = verify_pair(
            passing_metrics["pair_metrics"],
            passing_metrics["unhedged_stats"],
            passing_metrics["hedged_stats"],
        )
        assert result["approved"] is True
        assert len(result["failed_checks"]) == 0

    def test_low_correlation_rejected(self, failing_correlation):
        """A pair with low correlation should be rejected."""
        result = verify_pair(
            failing_correlation["pair_metrics"],
            failing_correlation["unhedged_stats"],
            failing_correlation["hedged_stats"],
        )
        assert result["approved"] is False
        assert any("correlation" in c.lower() for c in result["failed_checks"])

    def test_high_hedged_beta_rejected(self, passing_metrics):
        """A pair with high realized beta should be rejected."""
        passing_metrics["hedged_stats"]["realized_beta"] = 0.50  # Above 0.15
        result = verify_pair(
            passing_metrics["pair_metrics"],
            passing_metrics["unhedged_stats"],
            passing_metrics["hedged_stats"],
        )
        assert result["approved"] is False

    def test_weak_drawdown_reduction_rejected(self, passing_metrics):
        """A pair where hedged MDD > 50% of unhedged MDD should be rejected."""
        passing_metrics["hedged_stats"]["max_drawdown_pct"] = -20.0  # 66% of -30
        result = verify_pair(
            passing_metrics["pair_metrics"],
            passing_metrics["unhedged_stats"],
            passing_metrics["hedged_stats"],
        )
        assert result["approved"] is False

    def test_result_structure(self, passing_metrics):
        """Result should have required keys."""
        result = verify_pair(
            passing_metrics["pair_metrics"],
            passing_metrics["unhedged_stats"],
            passing_metrics["hedged_stats"],
        )
        assert "approved" in result
        assert "failed_checks" in result
        assert "diagnostic" in result
