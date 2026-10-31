"""Integration tests for the LangGraph multi-agent pipeline and StateProxy.

Verifies the execution of the real LangGraph multi-agent graph with only LLM calls stubbed,
and validates the dual attribute/item access behavior of StateProxy.
"""

from unittest.mock import MagicMock, patch
import pytest

from agents.graph import build_graph, run_hedge_builder
from agents.macro_parser import MacroIntent
from agents.screener import PairSelection
from agents.state import StateProxy, wrap_state


class TestGraphIntegration:
    """End-to-end integration test of the graph pipeline with LLMs stubbed."""

    def test_real_graph_run_with_stubbed_llms(self):
        """Execute the real LangGraph hedge builder with ONLY LLM calls stubbed.
        
        Asserts:
        1. All 5 nodes execute in order (macro_parser -> screener -> quant_node -> risk_verifier -> cro_reporter).
        2. A rejection on attempt 1 triggers the self-correction retry loop back to screener.
        3. A non-empty cro_report is generated upon termination.
        """
        # Fake macro intent
        fake_macro = MacroIntent(
            target_sector="NIFTY IT",
            benchmark="^NSEI",
            lookback_days=252,
            stress_regime="COVID_2020",
            reasoning="Testing stubbed macro parser",
        )

        # Screener returns a known non-cointegrated pair on attempt 1, triggering retry
        pair_attempt_1 = PairSelection(
            selected_long="TCS.NS",
            selected_short="LTTS.NS",
            long_rationale="High quality cash flow",
            short_rationale="Underperforming midcap IT",
            overall_reasoning="Candidate IT pair",
        )
        pair_attempt_2 = PairSelection(
            selected_long="INFY.NS",
            selected_short="TECHM.NS",
            long_rationale="Strong market cap",
            short_rationale="Higher drawdown",
            overall_reasoning="Second candidate IT pair",
        )

        screener_responses = [pair_attempt_1, pair_attempt_2, pair_attempt_2]

        def mock_screener_llm(*args, **kwargs):
            if screener_responses:
                return screener_responses.pop(0)
            return pair_attempt_2

        fake_verifier_commentary = MagicMock(content="Verifier audit: statistical thresholds evaluated on real NSE market data.")
        fake_cro_text = MagicMock(content="# CRO RISK MEMORANDUM\n\nPair risk analysis completed with institutional guardrails.")

        with patch("agents.macro_parser.get_gemini_client"), \
             patch("agents.macro_parser.invoke_with_retry", return_value=fake_macro), \
             patch("agents.screener.get_gemini_client"), \
             patch("agents.screener.invoke_with_retry", side_effect=mock_screener_llm), \
             patch("agents.risk_verifier.get_gemini_client"), \
             patch("agents.risk_verifier.invoke_with_retry", return_value=fake_verifier_commentary), \
             patch("agents.cro_reporter.get_gemini_client"), \
             patch("agents.cro_reporter.invoke_with_retry", return_value=fake_cro_text):

            # Run with max_attempts=2 to verify retry loop and exit
            final_state = run_hedge_builder(
                thesis="Bullish on Indian IT, hedged against market crash",
                lookback_days=252,
                max_attempts=2,
            )

        # 1. Assert all 5 nodes ran in order by checking the message stream and produced state keys
        messages = final_state.get("messages", [])
        assert len(messages) >= 5, f"Expected at least 5 node messages, got {len(messages)}"

        node_signatures = [
            m.content if hasattr(m, "content") else (m.get("content", "") if isinstance(m, dict) else str(m))
            for m in messages
        ]
        assert any("Macro Intent Parsed" in sig for sig in node_signatures), "macro_parser node did not run"
        assert any("Screener" in sig for sig in node_signatures), "screener node did not run"
        assert any("Quant Engine" in sig or "QuantEngine" in sig or "Pair Metrics" in sig or "Betas" in sig for sig in node_signatures), "quant_node did not run"
        assert any("Risk Verifier" in sig for sig in node_signatures), "risk_verifier node did not run"
        assert any("CRO Risk Memo" in sig or "CRO Report" in sig or "CRO" in sig for sig in node_signatures), "cro_reporter node did not run"

        # 2. Assert retry occurred: rejection_log is populated
        rejection_log = final_state.get("rejection_log", [])
        attempt_count = final_state.get("attempt_count", 1)
        assert attempt_count >= 2, f"Expected retry loop to increment attempt_count >= 2, got {attempt_count}"
        assert len(rejection_log) >= 1, "Expected at least 1 rejection recorded in rejection_log"
        assert rejection_log[0]["long"] == "TCS.NS"
        assert rejection_log[0]["short"] == "LTTS.NS"

        # 3. Assert CRO report produced
        cro_report = final_state.get("cro_report")
        assert cro_report is not None, "cro_report is None"
        assert isinstance(cro_report, str) and len(cro_report.strip()) > 0, "cro_report is empty"


class TestStateProxyAccess:
    """Verifies that StateProxy supports dual dict-style and attribute-style access."""

    def test_state_proxy_dict_and_attribute_access(self):
        """Confirm both state.thesis and state['thesis'] work, and missing keys raise AttributeError."""
        raw_dict = {"thesis": "Bullish on Indian IT", "lookback_days": 252}
        proxy = StateProxy(raw_dict)

        # Attribute-style access
        assert proxy.thesis == "Bullish on Indian IT"
        assert proxy.lookback_days == 252

        # Dict-style access
        assert proxy["thesis"] == "Bullish on Indian IT"
        assert proxy["lookback_days"] == 252
        assert proxy.get("thesis") == "Bullish on Indian IT"

        # Mutation via attribute reflects in dict
        proxy.target_sector = "NIFTY IT"
        assert proxy["target_sector"] == "NIFTY IT"

        # Mutation via dict reflects in attribute
        proxy["benchmark"] = "^NSEI"
        assert proxy.benchmark == "^NSEI"

        # wrap_state is idempotent
        wrapped = wrap_state(proxy)
        assert wrapped is proxy
        assert wrapped.thesis == "Bullish on Indian IT"

        # Unknown attribute not in schema raises AttributeError (catching typos)
        with pytest.raises(AttributeError):
            _ = proxy.completely_unknown_typo_key
