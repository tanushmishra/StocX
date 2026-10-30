"""Integration tests for the LangGraph multi-agent pipeline."""

from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd
import pytest

from agents.graph import build_graph, run_hedge_builder, should_continue_or_retry


class TestGraphRouter:
    """Tests for the conditional routing edge."""

    def test_routes_to_cro_reporter_when_approved(self):
        state_dict = {"approved": True, "attempt_count": 1, "max_attempts": 5}
        assert should_continue_or_retry(state_dict) == "cro_reporter"

    def test_routes_to_screener_when_rejected_and_attempts_remain(self):
        state_dict = {"approved": False, "attempt_count": 1, "max_attempts": 5}
        assert should_continue_or_retry(state_dict) == "screener"

    def test_routes_to_cro_reporter_when_attempts_exhausted(self):
        state_dict = {"approved": False, "attempt_count": 5, "max_attempts": 5}
        assert should_continue_or_retry(state_dict) == "cro_reporter"


class TestFullPipelineEndToEnd:
    """End-to-end integration tests for run_hedge_builder with mocked nodes/data."""

    @pytest.fixture
    def mock_prices(self):
        dates = pd.date_range("2024-01-01", periods=100, freq="B")
        df = pd.DataFrame(
            {
                "INFY.NS": np.linspace(1400, 1500, 100),
                "WIPRO.NS": np.linspace(400, 420, 100),
                "TCS.NS": np.linspace(3500, 3600, 100),
                "^NSEI": np.linspace(20000, 21000, 100),
            },
            index=dates,
        )
        df.attrs["data_source"] = "yfinance"
        df.attrs["is_synthetic"] = False
        return df

    def test_build_graph_compiles(self):
        app = build_graph()
        assert app is not None

    def test_run_hedge_builder_success(self, mock_prices):
        """End-to-end run where pair passes verification on attempt 1."""
        from agents.macro_parser import MacroIntent
        from agents.screener import PairSelection

        mock_macro = MacroIntent(
            target_sector="NIFTY IT",
            benchmark="^NSEI",
            lookback_days=100,
            stress_regime="COVID_2020",
            reasoning="Testing pipeline",
        )
        mock_pair = PairSelection(
            selected_long="INFY.NS",
            selected_short="WIPRO.NS",
            long_rationale="Strong balance sheet",
            short_rationale="Weaker margins",
            overall_reasoning="IT sector pair",
        )

        with patch("agents.macro_parser.get_gemini_client"), patch(
            "agents.macro_parser.invoke_with_retry", return_value=mock_macro
        ), patch("agents.screener.get_sector_constituents", return_value=["INFY.NS", "WIPRO.NS"]), patch(
            "agents.screener.get_fundamentals",
            return_value={"pe_ratio": 25.0, "roe": 0.25, "revenue_growth": 0.08, "debt_to_equity": 0.1, "data_source": "yfinance", "is_synthetic": False},
        ), patch(
            "agents.screener.fetch_ticker_news", return_value=[]
        ), patch(
            "agents.screener.get_gemini_client"
        ), patch(
            "agents.screener.invoke_with_retry", return_value=mock_pair
        ), patch(
            "engine.data_fetcher.fetch_prices", return_value=mock_prices
        ), patch(
            "engine.verifier.verify_pair",
            return_value={
                "approved": True,
                "reason": "All gates passed",
                "gates": {"correlation": True, "cointegration": True},
            },
        ), patch(
            "agents.risk_verifier.get_gemini_client"
        ), patch(
            "agents.risk_verifier.invoke_with_retry", return_value=MagicMock(content="Verified commentary")
        ), patch(
            "agents.cro_reporter.get_gemini_client"
        ), patch(
            "agents.cro_reporter.invoke_with_retry", return_value=MagicMock(content="# CRO Report: Pair Approved")
        ):
            final_state = run_hedge_builder("Bullish on Indian IT", max_attempts=3)

            assert final_state["approved"] is True
            assert final_state["attempt_count"] == 1
            assert final_state["selected_long"] == "INFY.NS"
            assert final_state["selected_short"] == "WIPRO.NS"
            assert "cro_report" in final_state
            assert "Pair Approved" in final_state["cro_report"]
            assert final_state["data_source"] == "yfinance"

    def test_run_hedge_builder_self_correction_loop(self, mock_prices):
        """Pipeline rejects first pair and loops back to screener, approving second pair."""
        from agents.macro_parser import MacroIntent
        from agents.screener import PairSelection

        mock_macro = MacroIntent(
            target_sector="NIFTY IT",
            benchmark="^NSEI",
            lookback_days=100,
            stress_regime="COVID_2020",
            reasoning="Testing self-correction loop",
        )

        pair_attempt_1 = PairSelection(
            selected_long="INFY.NS",
            selected_short="WIPRO.NS",
            long_rationale="Pick 1",
            short_rationale="Short 1",
            overall_reasoning="Attempt 1",
        )
        pair_attempt_2 = PairSelection(
            selected_long="TCS.NS",
            selected_short="WIPRO.NS",
            long_rationale="Pick 2",
            short_rationale="Short 2",
            overall_reasoning="Attempt 2",
        )

        with patch("agents.macro_parser.get_gemini_client"), patch(
            "agents.macro_parser.invoke_with_retry", return_value=mock_macro
        ), patch(
            "agents.screener.get_sector_constituents",
            return_value=["TCS.NS", "INFY.NS", "WIPRO.NS"],
        ), patch(
            "agents.screener.get_fundamentals",
            return_value={"pe_ratio": 25.0, "roe": 0.25, "revenue_growth": 0.08, "debt_to_equity": 0.1, "data_source": "yfinance", "is_synthetic": False},
        ), patch(
            "agents.screener.fetch_ticker_news", return_value=[]
        ), patch(
            "agents.screener.get_gemini_client"
        ), patch(
            "agents.screener.invoke_with_retry",
            side_effect=[pair_attempt_1, pair_attempt_2],
        ), patch(
            "engine.data_fetcher.fetch_prices", return_value=mock_prices
        ), patch(
            "engine.verifier.verify_pair",
            side_effect=[
                {"approved": False, "reason": "Failed cointegration test (p > 0.05)", "gates": {"cointegration": False}},
                {"approved": True, "reason": "Passed all gates", "gates": {"cointegration": True}},
            ],
        ), patch(
            "agents.risk_verifier.get_gemini_client"
        ), patch(
            "agents.risk_verifier.invoke_with_retry", return_value=MagicMock(content="Commentary")
        ), patch(
            "agents.cro_reporter.get_gemini_client"
        ), patch(
            "agents.cro_reporter.invoke_with_retry", return_value=MagicMock(content="# CRO Report: Success after loop")
        ):
            final_state = run_hedge_builder("Bullish on Indian IT", max_attempts=3)

            assert final_state["approved"] is True
            assert final_state["attempt_count"] == 2
            assert len(final_state["rejection_log"]) == 1
            assert final_state["rejection_log"][0]["long"] == "INFY.NS"
            assert final_state["rejection_log"][0]["short"] == "WIPRO.NS"
            assert final_state["selected_long"] == "TCS.NS"
