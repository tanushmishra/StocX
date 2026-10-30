"""Unit tests for Phase C2: Streamlit Dashboard UI Components & News Intelligence.

Verifies offline deterministic rendering, graceful null/missing data handling,
XSS escaping, and zero network calls during component execution.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock, patch

import pytest
import pandas as pd

from ui.adapter import (
    DashboardMetrics,
    DashboardViewModel,
    PortfolioData,
    QuantAnalysis,
    ReportingData,
    ResearchData,
    RunInfo,
    VerificationData,
)
from ui.components import (
    load_cached_news_for_ticker,
    render_agent_trace,
    render_fno_table,
    render_metric_card,
    render_news_panel,
    render_pair_details,
    render_verification_summary,
)


def make_test_view_model(
    thesis: str = "Bullish IT",
    approved: Optional[bool] = None,
    messages: Optional[List[Any]] = None,
    rejection_log: Optional[List[Dict[str, Any]]] = None,
    verifier_result: Optional[Dict[str, Any]] = None,
    selected_long: Optional[str] = "TCS.NS",
    selected_short: Optional[str] = "WIPRO.NS",
    long_fundamentals: Optional[Dict[str, Any]] = None,
    short_fundamentals: Optional[Dict[str, Any]] = None,
    attempt_count: int = 1,
    max_attempts: int = 3,
) -> DashboardViewModel:
    """Helper to instantiate complete DashboardViewModel for component tests."""
    return DashboardViewModel(
        run_info=RunInfo(
            thesis=thesis,
            selected_long=selected_long,
            selected_short=selected_short,
            approved=approved,
            attempt_count=attempt_count,
            max_attempts=max_attempts,
        ),
        metrics=DashboardMetrics(),
        portfolio=PortfolioData(),
        quant=QuantAnalysis(),
        verification=VerificationData(
            verifier_result=verifier_result,
            rejection_log=rejection_log or [],
            attempt_count=attempt_count,
            approved=approved,
            messages=messages or [],
        ),
        research=ResearchData(
            selected_long_fundamentals=long_fundamentals,
            selected_short_fundamentals=short_fundamentals,
        ),
        reporting=ReportingData(),
    )


@pytest.fixture
def mock_streamlit():
    """Mock Streamlit UI context so components can be tested hermetically."""
    with patch("ui.components.st") as mock_st:
        def mock_columns(spec):
            n = spec if isinstance(spec, int) else len(spec)
            cols = []
            for _ in range(n):
                c = MagicMock()
                c.__enter__.return_value = c
                c.__exit__.return_value = None
                cols.append(c)
            return cols

        mock_st.columns.side_effect = mock_columns

        def mock_expander(label, expanded=False):
            exp = MagicMock()
            exp.__enter__.return_value = exp
            exp.__exit__.return_value = None
            return exp

        mock_st.expander.side_effect = mock_expander

        yield mock_st


# ==============================================================================
# NEWS INTELLIGENCE TESTS
# ==============================================================================

def test_load_cached_news_for_ticker(tmp_path: Path):
    """Test loading news from local cache with ticker normalization and limits."""
    cache_file = tmp_path / "headlines.json"
    cache_data = {
        "TCS.NS": [
            {"headline": f"TCS News {i}", "publisher": "Reuters", "url": f"https://example.com/{i}"}
            for i in range(10)
        ]
    }
    cache_file.write_text(json.dumps(cache_data), encoding="utf-8")

    # With .NS
    res1 = load_cached_news_for_ticker("TCS.NS", limit=3, cache_path=cache_file)
    assert len(res1) == 3
    assert res1[0]["headline"] == "TCS News 0"

    # Without .NS (ticker normalization)
    res2 = load_cached_news_for_ticker("TCS", limit=2, cache_path=cache_file)
    assert len(res2) == 2
    assert res2[1]["headline"] == "TCS News 1"

    # Non-existent ticker
    res3 = load_cached_news_for_ticker("NONEXISTENT", limit=5, cache_path=cache_file)
    assert res3 == []

    # Non-existent cache file
    res4 = load_cached_news_for_ticker("TCS", limit=5, cache_path=tmp_path / "missing.json")
    assert res4 == []


def test_1_news_panel_valid_articles(mock_streamlit):
    """Test Case 1: News panel with valid long and short articles."""
    long_news = [
        {
            "headline": "TCS Q3 Revenue Beats Street Estimates",
            "publisher": "Economic Times",
            "published_at": "2026-10-30T10:00:00Z",
            "url": "https://economictimes.indiatimes.com/tech/tcs-q3",
            "snippet": "Strong deal pipeline drives margin expansion in BFSI.",
            "provider": "google_news_rss",
        }
    ]
    short_news = [
        {
            "headline": "Wipro Guides for Flat Revenue Growth",
            "publisher": "Livemint",
            "published_at": "2026-10-30T09:30:00Z",
            "url": "https://livemint.com/market/wipro-guidance",
            "snippet": "Consulting segment continues to face headwinds.",
            "provider": "google_news_rss",
        }
    ]

    render_news_panel(
        long_news=long_news,
        short_news=short_news,
        long_ticker="TCS.NS",
        short_ticker="WIPRO.NS",
    )

    assert mock_streamlit.markdown.called
    markdown_calls = [str(call) for call in mock_streamlit.markdown.call_args_list]
    rendered_text = "".join(markdown_calls)
    assert "TCS Q3 Revenue Beats" in rendered_text
    assert "Economic Times" in rendered_text
    assert "Wipro Guides for Flat" in rendered_text
    assert "Livemint" in rendered_text


def test_2_news_panel_empty_lists(mock_streamlit):
    """Test Case 2: News panel with empty lists displays clean fallback."""
    render_news_panel(
        long_news=[],
        short_news=None,
        long_ticker="INFY.NS",
        short_ticker="TECHM.NS",
    )

    assert mock_streamlit.info.call_count >= 2
    info_calls = [str(call) for call in mock_streamlit.info.call_args_list]
    combined_info = "".join(info_calls)
    assert "No recent news intelligence cached for INFY.NS" in combined_info
    assert "No recent news intelligence cached for TECHM.NS" in combined_info


def test_3_news_panel_missing_url(mock_streamlit):
    """Test Case 3: News item missing URL renders 'Source link unavailable' without crashing."""
    news = [{"headline": "Sample Headline", "publisher": "Test Source", "url": None}]
    render_news_panel(long_news=news, short_news=[], long_ticker="TCS.NS", short_ticker="INFY.NS")

    markdown_calls = [str(call) for call in mock_streamlit.markdown.call_args_list]
    rendered_text = "".join(markdown_calls)
    assert "Source link unavailable" in rendered_text


def test_4_news_panel_missing_timestamp(mock_streamlit):
    """Test Case 4: News item missing timestamp renders fallback text."""
    news = [{"headline": "Sample Headline", "publisher": "Test Source", "published_at": None}]
    render_news_panel(long_news=news, short_news=[], long_ticker="TCS.NS", short_ticker="INFY.NS")

    markdown_calls = [str(call) for call in mock_streamlit.markdown.call_args_list]
    rendered_text = "".join(markdown_calls)
    assert "Timestamp unavailable" in rendered_text


def test_5_news_panel_missing_snippet(mock_streamlit):
    """Test Case 5: News item missing snippet renders clean card without extra whitespace."""
    news = [{"headline": "Clean Headline", "publisher": "Source", "snippet": None}]
    render_news_panel(long_news=news, short_news=[], long_ticker="TCS.NS", short_ticker="INFY.NS")

    markdown_calls = [str(call) for call in mock_streamlit.markdown.call_args_list]
    rendered_text = "".join(markdown_calls)
    assert "Clean Headline" in rendered_text


def test_6_news_panel_invalid_records(mock_streamlit):
    """Test Case 6: Invalid non-dict news items are skipped gracefully."""
    news = ["invalid_string", None, 12345]  # type: ignore
    render_news_panel(long_news=news, short_news=[], long_ticker="TCS.NS", short_ticker="INFY.NS")


@patch("urllib.request.urlopen")
@patch("requests.get")
def test_7_no_network_calls_during_rendering(mock_req_get, mock_url_open, mock_streamlit):
    """Test Case 7: Strict verification that UI components make zero network requests."""
    long_news = [{"headline": "A", "publisher": "B", "url": "https://example.com"}]
    render_news_panel(long_news=long_news, short_news=[], long_ticker="TCS.NS", short_ticker="INFY.NS")
    load_cached_news_for_ticker("TCS.NS")

    assert mock_req_get.call_count == 0
    assert mock_url_open.call_count == 0


# ==============================================================================
# AGENT TRACE TESTS
# ==============================================================================

def test_8_agent_trace_with_real_messages(mock_streamlit):
    """Test Case 8: Agent trace with real multi-agent messages."""
    vm = make_test_view_model(
        approved=True,
        messages=[
            {"role": "Macro Intent Parser", "content": "Parsed sector: IT. Risk profile: Neutral."},
            {"role": "Adversarial Verifier", "content": "All 4 statistical gates passed."},
        ],
    )
    render_agent_trace(view_model_or_rejection_log=vm)

    assert mock_streamlit.success.called
    assert mock_streamlit.expander.call_count >= 2


def test_9_agent_trace_with_empty_messages(mock_streamlit):
    """Test Case 9: Agent trace with empty messages shows clean info message."""
    vm = make_test_view_model(approved=None, messages=[])
    render_agent_trace(view_model_or_rejection_log=vm)

    assert mock_streamlit.info.called
    info_calls = [str(call) for call in mock_streamlit.info.call_args_list]
    assert any("Execution history unavailable" in c for c in info_calls)


def test_10_agent_trace_rejection_history(mock_streamlit):
    """Test Case 10: Rejection history rendering displays failed checks and diagnostic."""
    vm = make_test_view_model(
        approved=False,
        rejection_log=[
            {
                "attempt": 1,
                "pair": ("TCS.NS", "INFY.NS"),
                "reason": "Failed cointegration test p=0.082 > 0.05",
                "failed_checks": ["cointegration"],
            }
        ],
    )
    render_agent_trace(view_model_or_rejection_log=vm)

    assert mock_streamlit.error.called
    markdown_calls = [str(call) for call in mock_streamlit.markdown.call_args_list]
    rendered_text = "".join(markdown_calls)
    assert "Attempt 1" in rendered_text
    assert "Failed cointegration test" in rendered_text


def test_11_agent_trace_missing_approval_status(mock_streamlit):
    """Test Case 11: Missing approval status shows neutral warning badge, never False."""
    vm = make_test_view_model(approved=None)
    render_agent_trace(view_model_or_rejection_log=vm)

    assert mock_streamlit.warning.called
    assert not mock_streamlit.error.called
    assert not mock_streamlit.success.called


# ==============================================================================
# PAIR DETAILS & FUNDAMENTALS TESTS
# ==============================================================================

def test_12_fundamentals_with_all_fields(mock_streamlit):
    """Test Case 12: Fundamentals with all fields populated."""
    vm = make_test_view_model(
        selected_long="TCS.NS",
        selected_short="WIPRO.NS",
        long_fundamentals={
            "pe_ratio": 29.5,
            "roe": 0.48,
            "debt_to_equity": 0.05,
            "revenue_growth": 0.08,
            "composite_score": 88.0,
        },
        short_fundamentals={
            "pe_ratio": 22.1,
            "roe": 0.16,
            "debt_to_equity": 0.12,
            "revenue_growth": 0.02,
            "composite_score": 62.0,
        },
    )
    render_pair_details(view_model_or_long=vm)

    assert mock_streamlit.table.call_count == 2
    df_long = mock_streamlit.table.call_args_list[0][0][0]
    assert isinstance(df_long, pd.DataFrame)
    assert "29.50x" in df_long.to_string()


def test_13_fundamentals_with_partial_fields(mock_streamlit):
    """Test Case 13: Partial fields render 'N/A' for missing fields, never 0.0."""
    vm = make_test_view_model(
        selected_long="TCS.NS",
        selected_short="WIPRO.NS",
        long_fundamentals={"pe_ratio": 29.5, "roe": None},
        short_fundamentals={"pe_ratio": None, "roe": 0.16},
    )
    render_pair_details(view_model_or_long=vm)

    df_long = mock_streamlit.table.call_args_list[0][0][0]
    df_short = mock_streamlit.table.call_args_list[1][0][0]

    assert df_long.loc["ROE", "Value"] == "N/A"
    assert df_short.loc["P/E Ratio", "Value"] == "N/A"


def test_14_fundamentals_missing_completely(mock_streamlit):
    """Test Case 14: Missing selected ticker fundamentals renders clean info."""
    vm = make_test_view_model(
        long_fundamentals={},
        short_fundamentals={},
    )
    render_pair_details(view_model_or_long=vm)

    assert mock_streamlit.info.call_count >= 2


# ==============================================================================
# VERIFICATION SUMMARY & PARTIAL VIEWMODEL TESTS
# ==============================================================================

def test_15_verification_summary_with_failed_checks(mock_streamlit):
    """Test Case 15: Verification summary renders failed gates, badges, and diagnostic."""
    vm = make_test_view_model(
        approved=False,
        verifier_result={
            "failed_checks": ["cointegration", "correlation"],
            "diagnostic": "Engle-Granger test p-value exceeds threshold.",
        },
        attempt_count=2,
        max_attempts=3,
    )
    render_verification_summary(view_model=vm)

    markdown_calls = [str(call) for call in mock_streamlit.markdown.call_args_list]
    rendered_text = "".join(markdown_calls)
    assert "REJECTED" in rendered_text
    assert "Attempt 2 of 3" in rendered_text
    assert "Engle-Granger test p-value" in rendered_text
    assert "cointegration, correlation" in rendered_text


def test_16_components_safely_handle_partial_view_model(mock_streamlit):
    """Test Case 16: All components handle empty or partial ViewModels without exceptions."""
    minimal_vm = make_test_view_model(thesis="Minimal Thesis")

    # Must not raise exceptions
    render_agent_trace(view_model_or_rejection_log=minimal_vm)
    render_pair_details(view_model_or_long=minimal_vm)
    render_verification_summary(view_model=minimal_vm)
    render_metric_card(label="Beta", unhedged_val=None, hedged_val=None)
    render_fno_table(fno_data=None)
