"""Unit tests for Data Fetcher provenance, caching, and fallback behaviour.

Validates Phase 2 requirements:
- Cache-first market data fetching.
- ALLOW_SYNTHETIC=false raises clear RuntimeError when cache misses and yfinance fails.
- ALLOW_SYNTHETIC=true allows synthetic fallback with 'synthetic_fallback' provenance.
- Synthetic prices are NEVER written to disk cache.
- Real fundamentals loaded from CSV; missing/blank/NaN remain None (never 0); missing ticker raises KeyError.
- Real NSE F&O lot sizes loaded from CSV with positive integer validation.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from agents.cro_reporter import cro_reporter_node
from agents.quant_node import quant_engine_node
from engine.data_fetcher import (
    _cache_path,
    audit_cache_directory,
    fetch_prices,
    get_data_source,
    get_fno_lot_sizes,
    get_fundamentals,
    is_synthetic_allowed,
    validate_cached_dataframe,
)


class TestDataFetcherProvenance:
    """Tests for data source provenance and cache safety."""

    @pytest.fixture
    def sample_dates(self):
        return pd.date_range("2024-01-01", "2024-01-10", freq="B")

    @pytest.fixture
    def mock_price_df(self, sample_dates):
        return pd.DataFrame(
            {
                "TCS.NS": np.linspace(3500, 3600, len(sample_dates)),
                "INFY.NS": np.linspace(1500, 1550, len(sample_dates)),
                "^NSEI": np.linspace(21000, 21500, len(sample_dates)),
            },
            index=sample_dates,
        )

    def test_live_data_provenance_and_cache_write(self, tmp_path, mock_price_df):
        """Live yfinance download must be tagged as 'yfinance' and saved to cache."""
        tickers = ["INFY.NS", "TCS.NS"]
        start = "2024-01-01"
        end = "2024-01-10"

        with patch("engine.data_fetcher._CACHE_DIR", tmp_path), patch("engine.data_fetcher.yf") as mock_yf:
            raw_mock = pd.DataFrame(
                {
                    ("Close", "INFY.NS"): mock_price_df["INFY.NS"].values,
                    ("Close", "TCS.NS"): mock_price_df["TCS.NS"].values,
                },
                index=mock_price_df.index,
            )
            mock_yf.download.return_value = raw_mock

            df = fetch_prices(tickers, start=start, end=end)

            assert get_data_source(df) == "yfinance"
            assert df.attrs["is_synthetic"] is False

            cache_label = "_".join(sorted(tickers))
            expected_cache = tmp_path / f"{cache_label}_{start}_{end}.csv"
            assert expected_cache.exists()

    def test_cached_data_provenance(self, tmp_path, mock_price_df):
        """Reading from cache must set data_source to 'cache' and not re-download."""
        tickers = ["INFY.NS", "TCS.NS"]
        start = "2024-01-01"
        end = "2024-01-10"

        cache_label = "_".join(sorted(tickers))
        cache_file = tmp_path / f"{cache_label}_{start}_{end}.csv"
        mock_price_df[["INFY.NS", "TCS.NS"]].to_csv(cache_file)

        with patch("engine.data_fetcher._CACHE_DIR", tmp_path), patch("engine.data_fetcher.yf") as mock_yf:
            df = fetch_prices(tickers, start=start, end=end)

            assert get_data_source(df) == "cache"
            assert df.attrs["is_synthetic"] is False
            mock_yf.download.assert_not_called()

    def test_synthetic_fallback_disabled_raises_runtime_error(self, tmp_path):
        """When live download fails and ALLOW_SYNTHETIC=false, raise descriptive RuntimeError."""
        tickers = ["INFY.NS", "TCS.NS"]
        start = "2024-01-01"
        end = "2024-01-10"

        with patch("engine.data_fetcher._CACHE_DIR", tmp_path), \
             patch("engine.data_fetcher.yf") as mock_yf, \
             patch("engine.data_fetcher.is_synthetic_allowed", return_value=False):
            mock_yf.download.side_effect = RuntimeError("Network disconnected")

            with pytest.raises(RuntimeError) as exc_info:
                fetch_prices(tickers, start=start, end=end)

            assert "ALLOW_SYNTHETIC=false" in str(exc_info.value)
            assert "Live market data fetch failed" in str(exc_info.value)

    def test_synthetic_fallback_provenance_when_allowed(self, tmp_path):
        """When yfinance fails and ALLOW_SYNTHETIC=true, synthetic fallback is tagged."""
        tickers = ["INFY.NS", "TCS.NS"]
        start = "2024-01-01"
        end = "2024-01-10"

        with patch("engine.data_fetcher._CACHE_DIR", tmp_path), \
             patch("engine.data_fetcher.yf") as mock_yf, \
             patch("engine.data_fetcher.is_synthetic_allowed", return_value=True):
            mock_yf.download.side_effect = RuntimeError("Network disconnected")

            df = fetch_prices(tickers, start=start, end=end)

            assert get_data_source(df) == "synthetic_fallback"
            assert df.attrs["is_synthetic"] is True
            assert not df.empty
            for t in tickers:
                assert t in df.columns

    def test_synthetic_data_never_persisted_to_cache(self, tmp_path):
        """CRITICAL: Synthetic fallback data must NEVER be written to the cache directory."""
        tickers = ["NONEXISTENT.NS", "TEST.NS"]
        start = "2024-01-01"
        end = "2024-01-10"

        with patch("engine.data_fetcher._CACHE_DIR", tmp_path), \
             patch("engine.data_fetcher.yf") as mock_yf, \
             patch("engine.data_fetcher.is_synthetic_allowed", return_value=True):
            mock_yf.download.return_value = pd.DataFrame()

            df = fetch_prices(tickers, start=start, end=end)
            assert df.attrs["is_synthetic"] is True

            saved_csvs = list(tmp_path.glob("*.csv"))
            assert len(saved_csvs) == 0, f"Synthetic CSV was erroneously saved: {saved_csvs}"

    def test_validate_cached_dataframe(self, sample_dates, mock_price_df):
        """validate_cached_dataframe returns True for valid price df, False for invalid."""
        assert validate_cached_dataframe(mock_price_df) is True
        assert validate_cached_dataframe(pd.DataFrame()) is False

        nan_df = pd.DataFrame({"A": [np.nan, np.nan]}, index=sample_dates[:2])
        assert validate_cached_dataframe(nan_df) is False

        neg_df = mock_price_df.copy()
        neg_df.iloc[0, 0] = -50.0
        assert validate_cached_dataframe(neg_df) is False

        flat_dates = pd.date_range("2024-01-01", periods=15, freq="B")
        flat_df = pd.DataFrame({"TCS.NS": [100.0] * 15}, index=flat_dates)
        assert validate_cached_dataframe(flat_df) is False

    def test_corrupted_cache_is_bypassed(self, tmp_path, mock_price_df):
        """If a cached CSV contains flat/corrupted data, fetch_prices bypasses it."""
        tickers = ["INFY.NS", "TCS.NS"]
        start = "2024-01-01"
        end = "2024-01-10"

        cache_label = "_".join(sorted(tickers))
        cache_file = tmp_path / f"{cache_label}_{start}_{end}.csv"
        flat_dates = pd.date_range(start, periods=12, freq="B")
        flat_df = pd.DataFrame({"INFY.NS": [100.0] * 12, "TCS.NS": [100.0] * 12}, index=flat_dates)
        flat_df.to_csv(cache_file)

        with patch("engine.data_fetcher._CACHE_DIR", tmp_path), patch("engine.data_fetcher.yf") as mock_yf:
            raw_mock = pd.DataFrame(
                {
                    ("Close", "INFY.NS"): mock_price_df["INFY.NS"].values,
                    ("Close", "TCS.NS"): mock_price_df["TCS.NS"].values,
                },
                index=mock_price_df.index,
            )
            mock_yf.download.return_value = raw_mock

            df = fetch_prices(tickers, start=start, end=end)
            assert get_data_source(df) == "yfinance"
            mock_yf.download.assert_called_once()

    def test_audit_cache_directory(self, tmp_path, mock_price_df):
        """audit_cache_directory must accurately report valid and invalid files."""
        valid_file = tmp_path / "valid_prices.csv"
        mock_price_df.to_csv(valid_file)

        invalid_file = tmp_path / "invalid_prices.csv"
        invalid_file.write_text("corrupted,header\nfoo,bar\n")

        audit = audit_cache_directory(tmp_path)
        assert audit["total_files"] == 2
        assert audit["valid_files"] == 1
        assert len(audit["invalid_files"]) == 1
        assert audit["invalid_files"][0]["file"] == "invalid_prices.csv"


class TestFundamentalsCSVLoading:
    """Tests for loading fundamentals from real CSV."""

    def test_fundamentals_loading_success(self):
        """get_fundamentals loads TCS.NS from data/fundamentals.csv."""
        fund = get_fundamentals("TCS.NS")
        assert fund["ticker"] == "TCS.NS"
        assert fund["data_source"] == "fundamentals_csv"
        assert fund["is_synthetic"] is False
        assert fund["pe_ratio"] is not None
        assert fund["pe_ratio"] > 0
        assert fund["roe"] is not None
        assert fund["roe"] > 0
        assert fund["market_cap"] is not None

    def test_fundamentals_preserves_none_for_blanks(self, tmp_path):
        """Blank, whitespace, or NaN cells must strictly remain None, never substituted with 0."""
        csv_file = tmp_path / "test_fundamentals.csv"
        csv_file.write_text(
            "ticker,company_name,market_cap,trailing_pe,forward_pe,return_on_equity,revenue_growth,debt_to_equity,profit_margins\n"
            "TEST.NS,Test Company,10000000,,   ,NaN,0.05,,0.15\n"
        )

        fund = get_fundamentals("TEST.NS", csv_path=csv_file)
        assert fund["ticker"] == "TEST.NS"
        assert fund["trailing_pe"] is None
        assert fund["forward_pe"] is None
        assert fund["pe_ratio"] is None
        assert fund["roe"] is None
        assert fund["revenue_growth"] == 0.05
        assert fund["debt_to_equity"] is None
        assert fund["profit_margins"] == 0.15

    def test_fundamentals_missing_ticker_raises_key_error(self):
        """Missing ticker raises KeyError for isolated handling in screener."""
        with pytest.raises(KeyError) as exc_info:
            get_fundamentals("UNKNOWN_TICKER_9999.NS")
        assert "UNKNOWN_TICKER_9999.NS" in str(exc_info.value)

    def test_fundamentals_missing_file_raises_filenotfound(self, tmp_path):
        """Non-existent CSV file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            get_fundamentals("TCS.NS", csv_path=tmp_path / "missing.csv")

    def test_fundamentals_malformed_csv_raises_value_error(self, tmp_path):
        """CSV without 'ticker' column raises ValueError."""
        csv_file = tmp_path / "bad.csv"
        csv_file.write_text("colA,colB\n1,2\n")
        with pytest.raises(ValueError):
            get_fundamentals("TCS.NS", csv_path=csv_file)


class TestLotSizesCSVLoading:
    """Tests for loading official NSE F&O lot sizes from CSV."""

    def test_lot_sizes_loading_success(self):
        """get_fno_lot_sizes loads official contract sizes from data/nse_lot_sizes.csv."""
        lots = get_fno_lot_sizes()
        assert isinstance(lots, dict)
        assert len(lots) >= 40
        assert lots.get("TCS.NS") == 225
        assert lots.get("INFY.NS") == 400
        for ticker, size in lots.items():
            assert isinstance(size, int)
            assert size > 0

    def test_lot_sizes_filters_invalids_and_duplicates(self, tmp_path):
        """Non-positive sizes, malformed values, and duplicates are handled correctly."""
        csv_file = tmp_path / "test_lots.csv"
        csv_file.write_text(
            "ticker,lot_size\n"
            "T1.NS,200\n"
            "T1.NS,300\n"  # Duplicate: retain first (200)
            "T2.NS,-50\n"   # Negative: skip
            "T3.NS,0\n"     # Zero: skip
            "T4.NS,invalid\n" # Non-numeric: skip
            "T5.NS,500.0\n" # Float string: convert to int 500
        )

        lots = get_fno_lot_sizes(csv_path=csv_file)
        assert lots["T1.NS"] == 200
        assert "T2.NS" not in lots
        assert "T3.NS" not in lots
        assert "T4.NS" not in lots
        assert lots["T5.NS"] == 500

    def test_lot_sizes_missing_file_raises_filenotfound(self, tmp_path):
        """Non-existent CSV file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            get_fno_lot_sizes(csv_path=tmp_path / "missing.csv")


class TestAgentDataProvenanceIntegration:
    """Integration checks for Quant Node and CRO Reporter data provenance."""

    def test_quant_node_captures_provenance(self):
        """Quant node must capture price data_source and store it in state."""
        sample_dates = pd.date_range("2024-01-01", periods=100, freq="B")
        mock_prices = pd.DataFrame(
            {
                "INFY.NS": np.linspace(1400, 1500, 100),
                "WIPRO.NS": np.linspace(400, 450, 100),
                "^NSEI": np.linspace(20000, 21000, 100),
            },
            index=sample_dates,
        )
        mock_prices.attrs["data_source"] = "synthetic_fallback"
        mock_prices.attrs["is_synthetic"] = True

        state = {
            "selected_long": "INFY.NS",
            "selected_short": "WIPRO.NS",
            "benchmark": "^NSEI",
            "lookback_days": 100,
            "stress_regime": "COVID_2020",
        }

        with patch("engine.data_fetcher.fetch_prices", return_value=mock_prices):
            result = quant_engine_node(state)
            assert result["data_source"] == "synthetic_fallback"

    def test_cro_reporter_synthetic_warning_fallback(self):
        """CRO Reporter fallback memo must include prominent warning if synthetic data."""
        state = {
            "thesis": "Bullish on IT",
            "target_sector": "NIFTY IT",
            "selected_long": "INFY.NS",
            "selected_short": "WIPRO.NS",
            "approved": True,
            "data_source": "synthetic_fallback",
            "attempt_count": 1,
            "max_attempts": 5,
        }

        with patch("langchain_google_genai.ChatGoogleGenerativeAI.invoke", side_effect=RuntimeError("no api key")):
            res = cro_reporter_node(state)
            report = res["cro_report"]
            assert "SYNTHETIC" in report.upper()
            assert "WARNING" in report.upper()
