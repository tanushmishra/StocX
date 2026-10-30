"""Unit tests for Dashboard State Adapter (ui.adapter).

Validates pure transformation from LangGraph state / engine outputs to DashboardViewModel,
ensuring strict zero-hallucination invariants, no silent zero substitution, type preservation
for pandas Series and DataFrames, robust handling of empty/partial states, and absolute purity
(no network, no LLM, no state mutation).
"""

from __future__ import annotations

import copy
from datetime import datetime, timezone
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from ui.adapter import (
    DashboardViewModel,
    map_state_to_dashboard,
)


# ────────────────────────────────────────────────────────────────────────────
# Realistic Fixtures Based on Actual Producer Contracts
# ────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_dates() -> pd.DatetimeIndex:
    return pd.bdate_range(start="2026-01-01", periods=10, name="Date")


@pytest.fixture
def verified_complete_state(sample_dates: pd.DatetimeIndex) -> dict:
    """Realistic complete state matching HedgeBuilderState and quant_node producers."""
    cum_hedged = pd.Series([1.0, 1.01, 1.02, 1.015, 1.025, 1.03, 1.035, 1.04, 1.045, 1.05], index=sample_dates)
    cum_unhedged = pd.Series([1.0, 0.98, 0.97, 0.99, 1.01, 0.95, 0.94, 0.96, 0.98, 1.02], index=sample_dates)
    spread_z = pd.Series([0.1, -0.4, 0.8, 1.2, 0.5, -0.2, -0.9, 0.3, 0.6, 0.2], index=sample_dates)
    rolling_beta = pd.Series([0.02, 0.01, 0.03, 0.01, 0.02, 0.01, 0.02, 0.01, 0.02, 0.01], index=sample_dates)
    corr_df = pd.DataFrame(
        [[1.0, 0.72, 0.68], [0.72, 1.0, 0.75], [0.68, 0.75, 1.0]],
        index=["INFY.NS", "TCS.NS", "^NSEI"],
        columns=["INFY.NS", "TCS.NS", "^NSEI"],
    )

    return {
        "thesis": "Bullish on Indian IT, hedged against crash",
        "target_sector": "NIFTY IT",
        "benchmark": "^NSEI",
        "lookback_days": 252,
        "stress_regime": "COVID_2020",
        "selected_long": "INFY.NS",
        "selected_short": "TCS.NS",
        "approved": True,
        "attempt_count": 1,
        "max_attempts": 5,
        "capital": 100000.0,
        "pair_metrics": {
            "static_beta_long": 1.15,
            "static_beta_short": 0.85,
            "spread_zscore": spread_z,
            "rolling_beta_long": rolling_beta,
            "correlation_matrix": corr_df,
            "cointegration": {
                "statistic": -3.85,
                "p_value": 0.012,
                "is_cointegrated": True,
            },
            "ou_half_life": 14.5,
        },
        "weights": {
            "long_weight": 0.425,
            "short_weight": -0.575,
            "portfolio_beta": 0.001,
        },
        "unhedged_stats": {
            "total_return": 0.125,
            "max_drawdown": -0.245,
            "annual_volatility": 0.215,
            "sharpe_ratio": 0.68,
            "sortino_ratio": 0.82,
            "realized_beta": 1.15,
            "var_95": -0.0185,
        },
        "hedged_stats": {
            "total_return": 0.082,
            "max_drawdown": -0.048,
            "annual_volatility": 0.065,
            "sharpe_ratio": 1.74,
            "sortino_ratio": 2.15,
            "realized_beta": 0.015,
            "var_95": -0.0052,
        },
        "cumulative_returns": {
            "hedged": cum_hedged,
            "unhedged": cum_unhedged,
        },
        "fno_execution": {
            "INFY.NS": {"lots": 2, "direction": "LONG", "notional_allocated": 42500.0},
            "TCS.NS": {"lots": 1, "direction": "SHORT", "notional_allocated": 57500.0},
        },
        "stress_results": {
            "max_drawdown_pct": -4.2,
            "recovery_days": 18,
        },
        "verifier_result": {
            "passed": True,
            "gates": {"correlation": True, "cointegration": True},
        },
        "rejection_log": [
            {"long": "WIPRO.NS", "short": "TCS.NS", "reason": "Low correlation"}
        ],
        "messages": [
            {"role": "assistant", "content": "Pair screened and approved."}
        ],
        "long_candidates": [
            {"ticker": "INFY.NS", "score": 8.5, "pe_ratio": 24.5, "roe": 0.32}
        ],
        "short_candidates": [
            {"ticker": "TCS.NS", "score": 6.2, "pe_ratio": 29.1, "roe": 0.44}
        ],
        "cro_report": "### Executive Memo\nStrategy approved for deployment.",
    }


# ────────────────────────────────────────────────────────────────────────────
# 1. Complete State with Verified Fields
# ────────────────────────────────────────────────────────────────────────────

def test_complete_state_with_verified_fields(verified_complete_state: dict):
    """Verify that all sections in ViewModel are correctly populated from complete state."""
    vm = map_state_to_dashboard(verified_complete_state)

    assert isinstance(vm, DashboardViewModel)

    # A. Run Info
    assert vm.run_info.thesis == "Bullish on Indian IT, hedged against crash"
    assert vm.run_info.target_sector == "NIFTY IT"
    assert vm.run_info.benchmark == "^NSEI"
    assert vm.run_info.lookback_days == 252
    assert vm.run_info.stress_regime == "COVID_2020"
    assert vm.run_info.selected_long == "INFY.NS"
    assert vm.run_info.selected_short == "TCS.NS"
    assert vm.run_info.approved is True
    assert vm.run_info.attempt_count == 1
    assert vm.run_info.max_attempts == 5
    assert vm.run_info.capital == 100000.0

    # B. Metrics
    assert vm.metrics.unhedged_beta == 1.15
    assert vm.metrics.hedged_beta == 0.015
    assert vm.metrics.unhedged_max_drawdown == -0.245
    assert vm.metrics.hedged_max_drawdown == -0.048
    assert vm.metrics.unhedged_sharpe == 0.68
    assert vm.metrics.hedged_sharpe == 1.74
    assert vm.metrics.unhedged_sortino == 0.82
    assert vm.metrics.hedged_sortino == 2.15
    assert vm.metrics.unhedged_volatility == 0.215
    assert vm.metrics.hedged_volatility == 0.065
    assert vm.metrics.unhedged_var_95 == -0.0185
    assert vm.metrics.hedged_var_95 == -0.0052

    # C. Portfolio
    assert vm.portfolio.weights["long_weight"] == 0.425
    assert "INFY.NS" in vm.portfolio.fno_execution

    # D. Quant Analysis
    assert vm.quant.half_life == 14.5
    assert vm.quant.cointegration["p_value"] == 0.012

    # E. Verification
    assert len(vm.verification.rejection_log) == 1
    assert vm.verification.approved is True

    # F. Research
    assert vm.research.selected_long_fundamentals["pe_ratio"] == 24.5
    assert vm.research.selected_short_fundamentals["roe"] == 0.44

    # G. Reporting
    assert "Executive Memo" in (vm.reporting.cro_report or "")


# ────────────────────────────────────────────────────────────────────────────
# 2. Empty State Handling
# ────────────────────────────────────────────────────────────────────────────

def test_empty_state():
    """Verify that empty state or None safely maps to None metrics and empty lists."""
    for empty_input in ({}, None):
        vm = map_state_to_dashboard(empty_input)

        assert isinstance(vm, DashboardViewModel)
        assert vm.run_info.thesis is None
        assert vm.run_info.approved is None
        assert vm.run_info.selected_long is None

        # All metrics must be None, NOT zero
        assert vm.metrics.unhedged_beta is None
        assert vm.metrics.hedged_beta is None
        assert vm.metrics.unhedged_max_drawdown is None
        assert vm.metrics.hedged_max_drawdown is None
        assert vm.metrics.unhedged_sharpe is None
        assert vm.metrics.hedged_sharpe is None

        # Collections must be empty structures, not None
        assert vm.verification.rejection_log == []
        assert vm.verification.messages == []
        assert vm.research.long_candidates == []
        assert vm.research.short_candidates == []

        # Time series / complex objects must be None
        assert vm.portfolio.cumulative_returns is None
        assert vm.quant.spread_zscore is None
        assert vm.quant.rolling_beta is None
        assert vm.quant.correlation_matrix is None


# ────────────────────────────────────────────────────────────────────────────
# 3. Partial State Handling
# ────────────────────────────────────────────────────────────────────────────

def test_partial_state():
    """Verify safe mapping when only screening stage has run."""
    partial_state = {
        "thesis": "Bullish Banking",
        "selected_long": "HDFCBANK.NS",
        "selected_short": "SBIN.NS",
        "attempt_count": 0,
        "max_attempts": 5,
    }
    vm = map_state_to_dashboard(partial_state)

    assert vm.run_info.thesis == "Bullish Banking"
    assert vm.run_info.selected_long == "HDFCBANK.NS"
    assert vm.run_info.selected_short == "SBIN.NS"
    assert vm.run_info.approved is None
    assert vm.metrics.unhedged_beta is None
    assert vm.metrics.hedged_sharpe is None
    assert vm.portfolio.weights is None


# ────────────────────────────────────────────────────────────────────────────
# 4. Missing Nested Dictionaries
# ────────────────────────────────────────────────────────────────────────────

def test_missing_nested_dictionaries():
    """Verify adapter handles state where nested dictionary keys are completely omitted."""
    state = {
        "selected_long": "INFY.NS",
        "selected_short": "TCS.NS",
        # pair_metrics, unhedged_stats, hedged_stats omitted
    }
    vm = map_state_to_dashboard(state)

    assert vm.run_info.selected_long == "INFY.NS"
    assert vm.metrics.unhedged_sharpe is None
    assert vm.quant.half_life is None
    assert vm.quant.pair_metrics == {}


# ────────────────────────────────────────────────────────────────────────────
# 5. Nested Values Explicitly Set to None
# ────────────────────────────────────────────────────────────────────────────

def test_nested_values_explicitly_set_to_none():
    """Verify adapter handles explicitly None nested values without TypeErrors."""
    state = {
        "unhedged_stats": {
            "sharpe_ratio": None,
            "max_drawdown": None,
            "realized_beta": None,
        },
        "hedged_stats": {
            "sharpe_ratio": None,
            "realized_beta": None,
        },
        "pair_metrics": {
            "cointegration": None,
            "ou_half_life": None,
            "spread_zscore": None,
        },
        "rejection_log": None,
        "messages": None,
        "cro_report": None,
    }
    vm = map_state_to_dashboard(state)

    assert vm.metrics.unhedged_sharpe is None
    assert vm.metrics.hedged_sharpe is None
    assert vm.metrics.unhedged_max_drawdown is None
    assert vm.quant.cointegration is None
    assert vm.quant.half_life is None
    assert vm.quant.spread_zscore is None
    assert vm.verification.rejection_log == []
    assert vm.verification.messages == []
    assert vm.reporting.cro_report is None


# ────────────────────────────────────────────────────────────────────────────
# 6. Missing Approval Status Remains None
# ────────────────────────────────────────────────────────────────────────────

def test_missing_approval_status_remains_none():
    """Verify that missing approval status remains None and is not defaulted to False."""
    state_no_approval = {"thesis": "Test thesis"}
    vm = map_state_to_dashboard(state_no_approval)
    assert vm.run_info.approved is None
    assert vm.verification.approved is None

    # Test explicit False is preserved
    state_false = {"thesis": "Test thesis", "approved": False}
    vm_false = map_state_to_dashboard(state_false)
    assert vm_false.run_info.approved is False
    assert vm_false.verification.approved is False

    # Test explicit True is preserved
    state_true = {"thesis": "Test thesis", "approved": True}
    vm_true = map_state_to_dashboard(state_true)
    assert vm_true.run_info.approved is True
    assert vm_true.verification.approved is True


# ────────────────────────────────────────────────────────────────────────────
# 7. Realistic pd.Series with DatetimeIndex
# ────────────────────────────────────────────────────────────────────────────

def test_realistic_pd_series_with_datetime_index(sample_dates: pd.DatetimeIndex):
    """Verify that pd.Series date indexes are preserved without destructive list conversion."""
    zscore_series = pd.Series([1.5, -0.5, 0.2, 1.8], index=sample_dates[:4], name="spread_z")
    hedged_cum = pd.Series([1.0, 1.01, 1.02, 1.03], index=sample_dates[:4], name="hedged_cum")

    state = {
        "pair_metrics": {"spread_zscore": zscore_series},
        "cumulative_returns": {"hedged": hedged_cum},
    }
    vm = map_state_to_dashboard(state)

    retrieved_z = vm.quant.spread_zscore
    assert isinstance(retrieved_z, pd.Series)
    assert len(retrieved_z) == 4
    assert retrieved_z.index.equals(sample_dates[:4])
    assert retrieved_z.iloc[0] == 1.5

    retrieved_cum = vm.portfolio.cumulative_returns
    assert isinstance(retrieved_cum["hedged"], pd.Series)
    assert retrieved_cum["hedged"].index.equals(sample_dates[:4])


# ────────────────────────────────────────────────────────────────────────────
# 8. Realistic pd.DataFrame with DatetimeIndex
# ────────────────────────────────────────────────────────────────────────────

def test_realistic_pd_dataframe_with_datetime_index():
    """Verify that correlation pd.DataFrame structures are preserved."""
    corr_df = pd.DataFrame(
        [[1.0, 0.85], [0.85, 1.0]],
        index=["TCS.NS", "INFY.NS"],
        columns=["TCS.NS", "INFY.NS"],
    )
    state = {
        "pair_metrics": {"correlation_matrix": corr_df}
    }
    vm = map_state_to_dashboard(state)

    retrieved_corr = vm.quant.correlation_matrix
    assert isinstance(retrieved_corr, pd.DataFrame)
    assert retrieved_corr.loc["TCS.NS", "INFY.NS"] == 0.85


# ────────────────────────────────────────────────────────────────────────────
# 9. Missing Metrics are Not Replaced by Zero
# ────────────────────────────────────────────────────────────────────────────

def test_missing_metrics_are_not_replaced_by_zero():
    """Verify strict zero-hallucination rule: uncomputed metrics must NEVER default to 0.00."""
    state = {
        "unhedged_stats": {},
        "hedged_stats": {},
    }
    vm = map_state_to_dashboard(state)

    assert vm.metrics.unhedged_beta is not 0.0
    assert vm.metrics.unhedged_beta is None
    assert vm.metrics.hedged_beta is not 0.0
    assert vm.metrics.hedged_beta is None
    assert vm.metrics.unhedged_max_drawdown is not 0.0
    assert vm.metrics.unhedged_max_drawdown is None
    assert vm.metrics.hedged_sharpe is not 0.0
    assert vm.metrics.hedged_sharpe is None
    assert vm.metrics.hedged_sortino is not 0.0
    assert vm.metrics.hedged_sortino is None

    # NaN must also be mapped to None, never 0.0
    state_with_nan = {
        "unhedged_stats": {"sharpe_ratio": float("nan"), "realized_beta": np.nan},
        "hedged_stats": {"max_drawdown": np.nan},
    }
    vm_nan = map_state_to_dashboard(state_with_nan)
    assert vm_nan.metrics.unhedged_sharpe is None
    assert vm_nan.metrics.unhedged_beta is None
    assert vm_nan.metrics.hedged_max_drawdown is None


# ────────────────────────────────────────────────────────────────────────────
# 10. Selected Ticker Fundamentals Extraction
# ────────────────────────────────────────────────────────────────────────────

def test_selected_ticker_fundamentals_extraction():
    """Verify that candidate records matching selected_long/selected_short are extracted."""
    state = {
        "selected_long": "INFY.NS",
        "selected_short": "WIPRO.NS",
        "long_candidates": [
            {"ticker": "INFY.NS", "score": 9.2, "pe_ratio": 24.1, "roe": 0.32},
            {"ticker": "TCS.NS", "score": 8.1, "pe_ratio": 28.5, "roe": 0.45},
        ],
        "short_candidates": [
            {"ticker": "WIPRO.NS", "score": 4.5, "pe_ratio": 21.0, "roe": 0.16},
            {"ticker": "TECHM.NS", "score": 4.8, "pe_ratio": 35.0, "roe": 0.12},
        ],
    }
    vm = map_state_to_dashboard(state)

    assert vm.research.selected_long_fundamentals is not None
    assert vm.research.selected_long_fundamentals["ticker"] == "INFY.NS"
    assert vm.research.selected_long_fundamentals["pe_ratio"] == 24.1

    assert vm.research.selected_short_fundamentals is not None
    assert vm.research.selected_short_fundamentals["ticker"] == "WIPRO.NS"
    assert vm.research.selected_short_fundamentals["roe"] == 0.16

    # When ticker is not in candidate list, returns None
    state_not_found = {
        "selected_long": "NONEXISTENT.NS",
        "long_candidates": [{"ticker": "INFY.NS"}],
    }
    vm_nf = map_state_to_dashboard(state_not_found)
    assert vm_nf.research.selected_long_fundamentals is None


# ────────────────────────────────────────────────────────────────────────────
# 11. Rejection Log Preservation
# ────────────────────────────────────────────────────────────────────────────

def test_rejection_log_preservation():
    """Verify rejection records and reasons are preserved verbatim."""
    rejections = [
        {"long": "TCS.NS", "short": "TECHM.NS", "reason": "Cointegration p=0.18 > 0.05"},
        {"long": "INFY.NS", "short": "WIPRO.NS", "reason": "Spread half-life 94 days > 60"},
    ]
    state = {"rejection_log": rejections}
    vm = map_state_to_dashboard(state)

    assert len(vm.verification.rejection_log) == 2
    assert vm.verification.rejection_log[0]["long"] == "TCS.NS"
    assert "Cointegration" in vm.verification.rejection_log[0]["reason"]
    assert vm.verification.rejection_log[1]["short"] == "WIPRO.NS"


# ────────────────────────────────────────────────────────────────────────────
# 12. Messages Preservation
# ────────────────────────────────────────────────────────────────────────────

def test_messages_preservation():
    """Verify agent execution messages are preserved in chronological order."""
    msgs = [
        {"role": "user", "content": "Build hedge for IT"},
        {"role": "assistant", "content": "MacroParser identified NIFTY IT"},
        {"role": "assistant", "content": "Screener selected INFY.NS / TCS.NS"},
    ]
    state = {"messages": msgs}
    vm = map_state_to_dashboard(state)

    assert len(vm.verification.messages) == 3
    assert vm.verification.messages[1]["content"] == "MacroParser identified NIFTY IT"


# ────────────────────────────────────────────────────────────────────────────
# 13. Input State Remains Unchanged After Mapping (No Mutation)
# ────────────────────────────────────────────────────────────────────────────

def test_input_state_remains_unchanged(verified_complete_state: dict):
    """Verify that map_state_to_dashboard is completely pure and does not mutate input state."""
    # Deep copy state snapshot
    original_state_copy = copy.deepcopy(verified_complete_state)

    # Execute mapping
    vm = map_state_to_dashboard(verified_complete_state)

    # Mutate viewmodel properties to ensure isolation
    if vm.portfolio.weights:
        vm.portfolio.weights["long_weight"] = 999.9
    if vm.research.selected_long_fundamentals:
        vm.research.selected_long_fundamentals["pe_ratio"] = 999.9

    # Assert original input state was not modified in any way
    assert verified_complete_state["weights"]["long_weight"] == original_state_copy["weights"]["long_weight"]
    assert verified_complete_state["long_candidates"][0]["pe_ratio"] == original_state_copy["long_candidates"][0]["pe_ratio"]
    assert verified_complete_state["thesis"] == original_state_copy["thesis"]
    assert verified_complete_state["approved"] == original_state_copy["approved"]


# ────────────────────────────────────────────────────────────────────────────
# 14. Adapter Does Not Invoke a Pipeline
# ────────────────────────────────────────────────────────────────────────────

def test_adapter_does_not_invoke_pipeline():
    """Verify that mapping does not call LangGraph or any pipeline execution node."""
    with patch("agents.graph.run_hedge_builder", side_effect=AssertionError("Should not call pipeline")):
        with patch("engine.hedge_pipeline.run_full_hedge_analysis", side_effect=AssertionError("Should not call pipeline")):
            vm = map_state_to_dashboard({"thesis": "Pure transformation test"})
            assert vm.run_info.thesis == "Pure transformation test"


# ────────────────────────────────────────────────────────────────────────────
# 15. Adapter Does Not Fetch Network Data
# ────────────────────────────────────────────────────────────────────────────

def test_adapter_does_not_fetch_network_data():
    """Verify that mapping performs zero socket/HTTP network calls."""
    with patch("requests.get", side_effect=AssertionError("Network call blocked")):
        with patch("requests.post", side_effect=AssertionError("Network call blocked")):
            with patch("urllib.request.urlopen", side_effect=AssertionError("Network call blocked")):
                vm = map_state_to_dashboard({"selected_long": "TCS.NS"})
                assert vm.run_info.selected_long == "TCS.NS"


# ────────────────────────────────────────────────────────────────────────────
# 16. Adapter Does Not Generate Synthetic Data
# ────────────────────────────────────────────────────────────────────────────

def test_adapter_does_not_generate_synthetic_data():
    """Verify that random numbers or mock generators are never invoked."""
    with patch("numpy.random.normal", side_effect=AssertionError("Random generation forbidden")):
        with patch("numpy.random.uniform", side_effect=AssertionError("Random generation forbidden")):
            vm = map_state_to_dashboard({"thesis": "Zero hallucination test"})
            assert vm.metrics.unhedged_beta is None
            assert vm.metrics.hedged_beta is None
            assert vm.portfolio.cumulative_returns is None
