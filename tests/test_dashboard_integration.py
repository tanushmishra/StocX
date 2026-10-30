"""Integration tests for Phase C3: Real Dashboard Integration & Synthetic Data Elimination.

Validates:
1. Pipeline to ViewModel mapping flow.
2. Full and partial ViewModel rendering in Streamlit.
3. Strict zero-synthetic-data invariants in app.py.
4. Exception and failure handling without demo fallbacks.
5. Real pandas Series and DataFrame chart rendering.
6. Zero network egress during dashboard execution.
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, call, patch

import numpy as np
import pandas as pd
import pytest

import app
from ui.adapter import (
    DashboardMetrics,
    DashboardViewModel,
    PortfolioData,
    QuantAnalysis,
    ReportingData,
    ResearchData,
    RunInfo,
    VerificationData,
    map_state_to_dashboard,
)
from ui.charts import (
    create_cumulative_returns_figure,
    create_drawdown_figure,
    create_rolling_beta_figure,
    create_zscore_figure,
)


@pytest.fixture
def mock_streamlit():
    """Mock Streamlit UI context for hermetic integration testing."""
    with patch("app.st") as mock_st, patch("ui.components.st") as mock_comp_st:
        session_dict: Dict[str, Any] = {}
        mock_st.session_state = session_dict
        mock_comp_st.session_state = session_dict

        def mock_columns(spec, **kwargs):
            n = spec if isinstance(spec, int) else len(spec)
            cols = []
            for _ in range(n):
                c = MagicMock()
                c.__enter__.return_value = c
                c.__exit__.return_value = None
                cols.append(c)
            return cols

        mock_st.columns.side_effect = mock_columns
        mock_comp_st.columns.side_effect = mock_columns

        def mock_expander(label, expanded=False):
            exp = MagicMock()
            exp.__enter__.return_value = exp
            exp.__exit__.return_value = None
            return exp

        mock_st.expander.side_effect = mock_expander
        mock_comp_st.expander.side_effect = mock_expander

        yield mock_st, mock_comp_st


@pytest.fixture
def sample_complete_pipeline_state() -> Dict[str, Any]:
    """Realistic LangGraph pipeline state output matching engine producers."""
    dates = pd.bdate_range(start="2026-01-01", periods=15, name="Date")
    hedged_cum = pd.Series([1.0 + 0.002 * i for i in range(15)], index=dates)
    unhedged_cum = pd.Series([1.0 + 0.005 * i for i in range(15)], index=dates)
    rolling_beta = pd.Series([0.02, 0.01, 0.02, -0.01, 0.00] * 3, index=dates)
    spread_z = pd.Series([0.1, 0.5, 1.2, -0.8, -1.6] * 3, index=dates)

    corr_df = pd.DataFrame(
        [[1.0, 0.78, 0.71], [0.78, 1.0, 0.69], [0.71, 0.69, 1.0]],
        index=["TCS.NS", "INFY.NS", "^NSEI"],
        columns=["TCS.NS", "INFY.NS", "^NSEI"],
    )

    return {
        "thesis": "Bullish Indian IT, hedge crash risk",
        "benchmark": "^NSEI",
        "lookback_days": 252,
        "stress_regime": "COVID_2020",
        "selected_long": "TCS.NS",
        "selected_short": "INFY.NS",
        "approved": True,
        "attempt_count": 1,
        "max_attempts": 5,
        "capital": 100000.0,
        "pair_metrics": {
            "static_beta_long": 1.15,
            "static_beta_short": 0.88,
            "rolling_beta_long": rolling_beta,
            "spread_zscore": spread_z,
            "correlation_matrix": corr_df,
            "cointegration": {"p_value": 0.015, "statistic": -3.72},
            "ou_half_life": 16.4,
        },
        "weights": {
            "long_weight": 0.433,
            "short_weight": -0.567,
            "portfolio_beta": 0.002,
        },
        "cumulative_returns": {
            "hedged": hedged_cum,
            "unhedged": unhedged_cum,
        },
        "backtest": {
            "hedged_metrics": {
                "sharpe": 1.82,
                "sortino": 2.14,
                "max_drawdown": -0.045,
                "annual_volatility": 0.078,
                "var_95": -0.008,
            },
            "unhedged_metrics": {
                "sharpe": 0.65,
                "sortino": 0.72,
                "max_drawdown": -0.245,
                "annual_volatility": 0.185,
                "var_95": -0.021,
            },
        },
        "fno_execution": [
            {"symbol": "TCS.NS", "direction": "LONG", "lot_size": 175, "lots": 1, "price": 3800.0, "notional": 665000},
            {"symbol": "INFY.NS", "direction": "SHORT", "lot_size": 400, "lots": 1, "price": 1500.0, "notional": 600000},
        ],
        "verifier_result": {
            "approved": True,
            "diagnostic": "All quantitative gates satisfied.",
            "failed_checks": [],
        },
        "rejection_log": [],
        "messages": [
            {"role": "Macro Intent Parser", "content": "Parsed sector: IT. Risk: Neutral."},
            {"role": "Adversarial Verifier", "content": "All 4 statistical gates passed."},
        ],
        "cro_report": "### CRO Report\nStrategy approved with 82% drawdown reduction.",
        "long_candidates": [{"ticker": "TCS.NS", "pe_ratio": 29.5, "roe": 0.48}],
        "short_candidates": [{"ticker": "INFY.NS", "pe_ratio": 22.1, "roe": 0.16}],
    }


# ==============================================================================
# INTEGRATION TESTS
# ==============================================================================

def test_1_pipeline_state_maps_to_view_model(sample_complete_pipeline_state):
    """Test 1: Verify actual pipeline state maps completely into DashboardViewModel."""
    vm = map_state_to_dashboard(sample_complete_pipeline_state, capital=100000.0)

    assert isinstance(vm, DashboardViewModel)
    assert vm.run_info.selected_long == "TCS.NS"
    assert vm.run_info.selected_short == "INFY.NS"
    assert vm.metrics.hedged_beta == 0.002
    assert vm.metrics.hedged_sharpe == 1.82
    assert vm.metrics.unhedged_sharpe == 0.65
    assert vm.verification.approved is True
    assert len(vm.verification.messages) == 2


def test_2_dashboard_renders_with_complete_view_model(mock_streamlit, sample_complete_pipeline_state):
    """Test 2: Dashboard renders all sections cleanly with a complete ViewModel."""
    mock_st, mock_comp_st = mock_streamlit
    vm = map_state_to_dashboard(sample_complete_pipeline_state, capital=100000.0)

    # Invoke dashboard renderer directly
    app._render_dashboard(vm)

    # Verification summary rendered
    assert mock_comp_st.markdown.called
    assert mock_comp_st.metric.called
    # Metric cards rendered
    assert mock_comp_st.table.called
    # Plotly charts rendered
    assert mock_comp_st.plotly_chart.call_count >= 3


def test_3_dashboard_handles_partial_state(mock_streamlit):
    """Test 3: Dashboard handles partial state without raising exceptions."""
    mock_st, mock_comp_st = mock_streamlit
    partial_state = {
        "thesis": "Bullish IT",
        "selected_long": "TCS.NS",
        "selected_short": None,
        "approved": None,
        "pair_metrics": {},
    }
    vm = map_state_to_dashboard(partial_state)

    # Rendering partial ViewModel must not raise
    app._render_dashboard(vm)
    assert mock_comp_st.markdown.called


def test_4_missing_metrics_render_safely(mock_streamlit):
    """Test 4: Missing metrics display 'N/A' and do not substitute zero."""
    mock_st, mock_comp_st = mock_streamlit
    empty_vm = map_state_to_dashboard({})

    app._render_dashboard(empty_vm)

    # Check rendered metric cards contain N/A
    markdown_calls = [str(call) for call in mock_comp_st.markdown.call_args_list]
    rendered = "".join(markdown_calls)
    assert "N/A" in rendered


@patch("app.run_hedge_builder")
def test_5_pipeline_exceptions_show_error_not_demo(mock_run, mock_streamlit):
    """Test 5: Pipeline exceptions show a clear error and never fall back to demo data."""
    mock_st, _ = mock_streamlit
    mock_run.side_effect = RuntimeError("Market data connection timeout")

    # Set up sidebar return and thesis inputs
    mock_st.text_input.return_value = "Bullish IT"
    mock_st.button.return_value = True

    with patch("app._render_sidebar") as mock_sb:
        mock_sb.return_value = {
            "capital": 100000.0,
            "lookback_days": 252,
            "benchmark": "^NSEI",
            "stress_regime": "COVID_2020",
        }
        app.main()

    # Verify error was logged and displayed, view_model is None
    assert mock_st.error.called
    assert "Market data connection timeout" in str(mock_st.error.call_args)
    assert mock_st.session_state.get("view_model") is None


@patch("app.run_hedge_builder")
def test_6_pipeline_not_called_twice(mock_run, mock_streamlit, sample_complete_pipeline_state):
    """Test 6: Pipeline is called exactly once per submission, and not on ordinary reruns."""
    mock_st, _ = mock_streamlit
    mock_run.return_value = sample_complete_pipeline_state

    # 1. First run: button clicked
    mock_st.text_input.return_value = "Bullish IT"
    mock_st.button.return_value = True

    with patch("app._render_sidebar") as mock_sb:
        mock_sb.return_value = {
            "capital": 100000.0,
            "lookback_days": 252,
            "benchmark": "^NSEI",
            "stress_regime": "COVID_2020",
        }
        app.main()

    assert mock_run.call_count == 1

    # 2. Subsequent rerun (user toggling a widget, button is False)
    mock_st.button.return_value = False
    with patch("app._render_sidebar") as mock_sb:
        mock_sb.return_value = {
            "capital": 100000.0,
            "lookback_days": 252,
            "benchmark": "^NSEI",
            "stress_regime": "COVID_2020",
        }
        app.main()

    # Call count must still be 1 (no re-execution on rerun)
    assert mock_run.call_count == 1


@patch("urllib.request.urlopen")
@patch("requests.get")
def test_7_news_rendering_zero_network_calls(mock_req, mock_urlopen, mock_streamlit, sample_complete_pipeline_state):
    """Test 7: Strict verification that news rendering makes zero network requests."""
    vm = map_state_to_dashboard(sample_complete_pipeline_state)
    app._render_dashboard(vm)

    assert mock_req.call_count == 0
    assert mock_urlopen.call_count == 0


def test_8_approval_status_matches_state(mock_streamlit, sample_complete_pipeline_state):
    """Test 8: Approval status is strictly taken from actual state (approved vs rejected vs none)."""
    _, mock_comp_st = mock_streamlit

    # 1. Approved state
    sample_complete_pipeline_state["approved"] = True
    vm_approved = map_state_to_dashboard(sample_complete_pipeline_state)
    app._render_dashboard(vm_approved)
    rendered_app = "".join(str(c) for c in mock_comp_st.markdown.call_args_list)
    assert "APPROVED ✅" in rendered_app

    # 2. Rejected state
    mock_comp_st.reset_mock()
    sample_complete_pipeline_state["approved"] = False
    vm_rejected = map_state_to_dashboard(sample_complete_pipeline_state)
    app._render_dashboard(vm_rejected)
    rendered_rej = "".join(str(c) for c in mock_comp_st.markdown.call_args_list)
    assert "REJECTED ❌" in rendered_rej


def test_9_charts_handle_real_pandas_series_with_datetime_index():
    """Test 9: Chart factory functions preserve real DatetimeIndex without crashing."""
    dates = pd.bdate_range(start="2026-01-01", periods=10, name="Date")
    ser = pd.Series([0.01 * i for i in range(10)], index=dates)

    fig_cum = create_cumulative_returns_figure(dates=dates, hedged_cum=ser.values, unhedged_cum=ser.values)
    assert fig_cum is not None
    assert len(fig_cum.data) == 2

    fig_beta = create_rolling_beta_figure(dates=dates, rolling_beta=ser.values)
    assert fig_beta is not None

    fig_z = create_zscore_figure(dates=dates, zscore=ser.values)
    assert fig_z is not None

    fig_dd = create_drawdown_figure(dates=dates, unhedged_dd=ser.values, hedged_dd=ser.values)
    assert fig_dd is not None


def test_10_charts_handle_empty_and_nan_inputs():
    """Test 10: Charts handle empty, None, and all-NaN inputs safely returning empty figures."""
    fig_empty = create_cumulative_returns_figure(dates=[], unhedged_cum=None, hedged_cum=None)
    assert fig_empty is not None
    assert len(fig_empty.data) == 0

    all_nan = np.array([np.nan, np.nan, np.nan])
    fig_nan = create_zscore_figure(dates=[1, 2, 3], zscore=all_nan)
    assert fig_nan is not None


def test_11_no_synthetic_data_generation_remains_in_app():
    """Test 11: Audit app module to confirm zero synthetic data functions or demo constants."""
    app_source = inspect.getsource(app)

    # Confirm _generate_demo_data does not exist
    assert "_generate_demo_data" not in app_source
    assert "np.random.normal" not in app_source
    assert "np.random.seed" not in app_source

    # Confirm hardcoded metrics are eliminated
    assert "beta_unhedged\":    1.12" not in app_source
    assert "max_dd_unhedged\": -28.4" not in app_source
    assert "sharpe_unhedged\":  0.65" not in app_source


def test_12_c1_and_c2_compatibility(mock_streamlit, sample_complete_pipeline_state):
    """Test 12: Verify C1 adapter and C2 components function together with 100% interoperability."""
    vm = map_state_to_dashboard(sample_complete_pipeline_state, capital=50000.0)

    # C1 ViewModel has all expected sections
    assert hasattr(vm, "run_info")
    assert hasattr(vm, "metrics")
    assert hasattr(vm, "portfolio")
    assert hasattr(vm, "quant")
    assert hasattr(vm, "verification")
    assert hasattr(vm, "research")
    assert hasattr(vm, "reporting")

    # Pass to C2 components without exception
    app._render_dashboard(vm)


# ==============================================================================
# SECTION 6 COMPREHENSIVE FAILURE & EDGE-CASE TESTS
# ==============================================================================

def test_13_empty_thesis_shows_warning(mock_streamlit):
    """Edge Case 1: Empty or whitespace thesis displays warning, does not run pipeline."""
    mock_st, _ = mock_streamlit
    mock_st.text_input.return_value = "   "
    mock_st.button.return_value = True

    with patch("app.run_hedge_builder") as mock_run, patch("app._render_sidebar") as mock_sb:
        mock_sb.return_value = {
            "capital": 100000.0,
            "lookback_days": 252,
            "benchmark": "^NSEI",
            "stress_regime": "COVID_2020",
        }
        app.main()

        assert mock_run.call_count == 0
        assert mock_st.warning.called
        assert "Please enter a market thesis" in str(mock_st.warning.call_args)


def test_14_missing_selected_tickers_fallback(mock_streamlit):
    """Edge Case 4: Missing selected tickers render fallback labels safely."""
    _, mock_comp_st = mock_streamlit
    state = {"thesis": "Test", "selected_long": None, "selected_short": None}
    vm = map_state_to_dashboard(state)

    app._render_dashboard(vm)

    markdown_calls = [str(call) for call in mock_comp_st.markdown.call_args_list]
    rendered = "".join(markdown_calls)
    assert "Long Leg" in rendered
    assert "Short Hedge" in rendered


def test_15_empty_cumulative_returns_and_corr_matrix(mock_streamlit):
    """Edge Cases 6 & 7: Empty cumulative returns and correlation matrix render clean notices."""
    _, mock_comp_st = mock_streamlit
    state = {
        "thesis": "Test",
        "cumulative_returns": None,
        "pair_metrics": {"correlation_matrix": None},
    }
    vm = map_state_to_dashboard(state)

    app._render_dashboard(vm)

    info_calls = [str(call) for call in mock_comp_st.info.call_args_list]
    rendered_info = "".join(info_calls)
    assert "No cumulative returns data available" in rendered_info
    assert "No correlation data available" in rendered_info


def test_16_missing_and_corrupt_news_cache(mock_streamlit, tmp_path):
    """Edge Cases 8 & 9: Missing or corrupt news cache handles safely returning empty lists."""
    from ui.components import load_cached_news_for_ticker

    # 1. Missing cache file
    missing_path = tmp_path / "nonexistent.json"
    items_missing = load_cached_news_for_ticker("TCS.NS", cache_path=missing_path)
    assert items_missing == []

    # 2. Corrupt JSON cache
    corrupt_path = tmp_path / "corrupt.json"
    corrupt_path.write_text("{invalid json corrupt content...", encoding="utf-8")
    items_corrupt = load_cached_news_for_ticker("TCS.NS", cache_path=corrupt_path)
    assert items_corrupt == []


def test_17_missing_cro_and_fno_execution(mock_streamlit):
    """Edge Cases 10, 11 & 12: Missing CRO report and F&O data show clean unavailable notices."""
    mock_st, mock_comp_st = mock_streamlit
    state = {
        "thesis": "Test",
        "cro_report": None,
        "fno_execution": None,
        "long_candidates": [],
        "short_candidates": [],
    }
    vm = map_state_to_dashboard(state)

    app._render_dashboard(vm)

    # Check CRO notice on app.st and F&O notice on ui.components.st
    app_info = "".join(str(c) for c in mock_st.info.call_args_list)
    comp_info = "".join(str(c) for c in mock_comp_st.info.call_args_list)

    assert "CRO executive summary memo is unavailable" in app_info
    assert "No F&O contract specifications available" in comp_info


def test_18_verifier_not_evaluated_status(mock_streamlit):
    """Edge Case 13: Verifier status not evaluated renders neutral status badge, not False."""
    _, mock_comp_st = mock_streamlit
    state = {"thesis": "Test", "approved": None}
    vm = map_state_to_dashboard(state)

    app._render_dashboard(vm)

    markdown_calls = [str(call) for call in mock_comp_st.markdown.call_args_list]
    rendered = "".join(markdown_calls)
    assert "NOT EVALUATED ⚪" in rendered


@patch("app.run_hedge_builder")
def test_19_new_thesis_clears_old_view_model_even_on_failure(mock_run, mock_streamlit, sample_complete_pipeline_state):
    """Edge Case 15: Submitting a new thesis clears previous ViewModel, ensuring no stale state."""
    mock_st, _ = mock_streamlit

    # 1. First run succeeds
    mock_run.return_value = sample_complete_pipeline_state
    mock_st.text_input.return_value = "Thesis 1"
    mock_st.button.return_value = True

    with patch("app._render_sidebar") as mock_sb:
        mock_sb.return_value = {
            "capital": 100000.0,
            "lookback_days": 252,
            "benchmark": "^NSEI",
            "stress_regime": "COVID_2020",
        }
        app.main()

    assert mock_st.session_state.get("view_model") is not None
    assert mock_st.session_state.get("last_thesis") == "Thesis 1"

    # 2. Second run for a different thesis fails with exception
    mock_run.side_effect = ValueError("Second run pipeline failure")
    mock_st.text_input.return_value = "Thesis 2"
    mock_st.button.return_value = True

    with patch("app._render_sidebar") as mock_sb:
        mock_sb.return_value = {
            "capital": 100000.0,
            "lookback_days": 252,
            "benchmark": "^NSEI",
            "stress_regime": "COVID_2020",
        }
        app.main()

    # Crucial: view_model must NOT be Thesis 1; it must be None!
    assert mock_st.session_state.get("view_model") is None
    assert mock_st.error.called
    assert "Second run pipeline failure" in str(mock_st.error.call_args)

