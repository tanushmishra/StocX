"""Unit tests for agents/screener.py."""

from unittest.mock import MagicMock, patch
import pytest

from agents.screener import (
    PairSelection,
    _fallback_selection,
    _format_candidates,
    _format_rejection_log,
    screener_node,
)


class TestScreenerFormatting:
    """Tests for table formatting and exclusion logging."""

    def test_format_candidates_table(self):
        candidates = [
            {
                "ticker": "INFY.NS",
                "score": 8.5,
                "pe_ratio": 24.0,
                "roe": 0.30,
                "revenue_growth": 0.08,
                "debt_to_equity": 0.10,
                "data_source": "yfinance",
            }
        ]
        table = _format_candidates(candidates)
        assert "INFY.NS" in table
        assert "8.50" in table
        assert "30.0%" in table
        assert "yfinance" in table

    def test_format_candidates_empty(self):
        assert "_No candidates available._" in _format_candidates([])

    def test_format_rejection_log(self):
        log = [{"long": "INFY.NS", "short": "WIPRO.NS", "reason": "Failed cointegration"}]
        formatted = _format_rejection_log(log)
        assert "INFY.NS" in formatted
        assert "WIPRO.NS" in formatted
        assert "Failed cointegration" in formatted

    def test_fallback_selection_skips_excluded(self):
        long_candidates = [{"ticker": "TCS.NS"}, {"ticker": "INFY.NS"}]
        short_candidates = [{"ticker": "WIPRO.NS"}, {"ticker": "TECHM.NS"}]
        excluded = {("TCS.NS", "WIPRO.NS")}

        long_pick, short_pick, reason = _fallback_selection(
            long_candidates, short_candidates, excluded
        )
        assert (long_pick, short_pick) != ("TCS.NS", "WIPRO.NS")
        assert (long_pick, short_pick) == ("TCS.NS", "TECHM.NS")


class TestScreenerNodeIntegration:
    """Tests for screener_node execution with dict states and fallbacks."""

    @pytest.fixture
    def mock_constituents(self):
        return ["TCS.NS", "INFY.NS", "WIPRO.NS", "TECHM.NS"]

    @pytest.fixture
    def mock_fundamentals(self):
        return {
            "pe_ratio": 25.0,
            "roe": 0.25,
            "revenue_growth": 0.08,
            "debt_to_equity": 0.05,
            "data_source": "yfinance",
            "is_synthetic": False,
        }

    def test_screener_node_with_dict_state_and_fallback(
        self, mock_constituents, mock_fundamentals
    ):
        state = {
            "thesis": "Bullish on Indian IT services",
            "target_sector": "NIFTY IT",
            "attempt_count": 0,
            "max_attempts": 5,
            "rejection_log": [],
        }

        with patch("agents.screener.get_sector_constituents", return_value=mock_constituents), patch(
            "agents.screener.get_fundamentals", return_value=mock_fundamentals
        ), patch(
            "agents.screener.fetch_ticker_news", return_value=[]
        ), patch(
            "agents.screener.get_gemini_client", side_effect=ValueError("No API key configured")
        ):
            res = screener_node(state)

            assert "selected_long" in res
            assert "selected_short" in res
            assert res["selected_long"] != ""
            assert res["selected_short"] != ""
            assert len(res["long_candidates"]) > 0
            assert len(res["short_candidates"]) > 0
            assert res["long_candidates"][0]["data_source"] == "yfinance"

    def test_screener_node_with_successful_llm(
        self, mock_constituents, mock_fundamentals
    ):
        state = {
            "thesis": "Bullish on Indian IT services",
            "target_sector": "NIFTY IT",
            "attempt_count": 0,
            "max_attempts": 5,
            "rejection_log": [],
        }

        mock_selection = PairSelection(
            selected_long="TCS.NS",
            selected_short="WIPRO.NS",
            long_rationale="Strong market leader with 45% ROE",
            short_rationale="Negative revenue growth and lower margins",
            overall_reasoning="Classic quality divergence pair trade",
        )

        with patch("agents.screener.get_sector_constituents", return_value=mock_constituents), patch(
            "agents.screener.get_fundamentals", return_value=mock_fundamentals
        ), patch(
            "agents.screener.fetch_ticker_news", return_value=[]
        ), patch(
            "agents.screener.get_gemini_client"
        ) as mock_get_client, patch(
            "agents.screener.invoke_with_retry", return_value=mock_selection
        ):
            res = screener_node(state)

            assert res["selected_long"] == "TCS.NS"
            assert res["selected_short"] == "WIPRO.NS"
            assert "TCS.NS" in res["messages"][0]["content"]
