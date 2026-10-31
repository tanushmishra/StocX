"""Unit tests for agents/macro_parser.py."""

from unittest.mock import MagicMock, patch
import pytest

from agents.macro_parser import MacroIntent, macro_parser_node


class TestMacroParserNode:
    """Tests for macro_parser_node execution and loud fallback handling."""

    def test_macro_parser_success_with_llm(self):
        """When LLM succeeds, llm_fallback_used must be False and trace clean."""
        mock_intent = MacroIntent(
            target_sector="NIFTY IT",
            benchmark="^NSEI",
            lookback_days=252,
            stress_regime="COVID_2020",
            reasoning="Tech sector thesis parsed via structured LLM.",
        )

        state = {"thesis": "Bullish on Indian IT, hedged against crash"}

        with patch("agents.macro_parser.get_gemini_client"), patch(
            "agents.macro_parser.invoke_with_retry", return_value=mock_intent
        ):
            res = macro_parser_node(state)

            assert res["target_sector"] == "NIFTY IT"
            assert res["benchmark"] == "^NSEI"
            assert res["lookback_days"] == 252
            assert res["stress_regime"] == "COVID_2020"
            assert res["llm_fallback_used"] is False
            assert "LLM unavailable" not in res["messages"][0]["content"]
            assert "Macro Intent Parsed" in res["messages"][0]["content"]

    def test_macro_parser_loud_fallback_when_llm_fails(self):
        """When LLM fails permanently, fallback must be loud with visible flag and trace banner."""
        state = {"thesis": "Bullish on Indian IT, hedged against crash"}

        with patch("agents.macro_parser.get_gemini_client"), patch(
            "agents.macro_parser.invoke_with_retry", side_effect=RuntimeError("503 UNAVAILABLE: high demand")
        ):
            res = macro_parser_node(state)

            # Heuristics still resolve correctly
            assert res["target_sector"] == "NIFTY IT"
            assert res["benchmark"] == "^NSEI"
            assert res["lookback_days"] == 252
            assert res["stress_regime"] == "COVID_2020"
            # Loud fallback flags
            assert res["llm_fallback_used"] is True
            trace_content = res["messages"][0]["content"]
            assert "LLM unavailable: heuristic defaults used" in trace_content
            assert "Macro Intent Parsed" in trace_content
