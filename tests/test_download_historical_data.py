"""
Unit tests for scripts/download_historical_data.py.
Verifies regime-agnostic drawdown calculation, missing-price NaN preservation,
transient retry handling, permanent error bypass, batch failure isolation, and overwrite safety.
"""

from unittest.mock import MagicMock, patch
import numpy as np
import pandas as pd
import pytest

from scripts.download_historical_data import (
    compute_max_drawdown,
    fetch_ticker_data,
    download_sector_regime,
    download_all_sectors_for_regime,
)


class TestRegimeAgnosticDrawdown:
    """Tests for compute_max_drawdown across various market windows."""

    def test_non_covid_regime_drawdown_calculation(self):
        """Should accurately compute peak, trough, and drawdown for any non-COVID regime."""
        dates = pd.date_range("2024-05-15", "2024-06-15", freq="B")
        # Synthesize a price series with known peak of 200.0 on day 2 and trough of 150.0 on day 8 (-25% drop)
        prices = [190.0, 200.0, 195.0, 180.0, 170.0, 160.0, 155.0, 150.0]
        prices += [165.0] * (len(dates) - len(prices))
        s = pd.Series(prices, index=dates)

        res = compute_max_drawdown(s)
        assert res["pre_crash_peak"] == 200.0
        assert res["crash_trough"] == 150.0
        assert res["max_drawdown_pct"] == -25.0
        assert res["crash_visible"] is True

    def test_empty_and_insufficient_series_gracefully_handled(self):
        """Should handle None, empty Series, and single-observation series without crashing."""
        res_none = compute_max_drawdown(None)
        assert res_none["max_drawdown_pct"] is None
        assert res_none["crash_visible"] is False

        res_empty = compute_max_drawdown(pd.Series([], dtype=float))
        assert res_empty["max_drawdown_pct"] is None

        res_single = compute_max_drawdown(pd.Series([100.0], index=[pd.Timestamp("2024-05-15")]))
        assert res_single["max_drawdown_pct"] is None


class TestMissingPricePolicy:
    """Tests confirming missing values are preserved as NaN and not zeroed or forward-filled."""

    @patch("scripts.download_historical_data.fetch_ticker_data")
    @patch("scripts.download_historical_data.DATA_DIR")
    def test_missing_prices_remain_nan(self, mock_data_dir, mock_fetch, tmp_path):
        """Missing prices must remain NaN/blank without zero-filling or forward-filling."""
        mock_data_dir.__truediv__.side_effect = lambda f: tmp_path / f

        # Synthetic calendar with 5 days
        calendar = pd.date_range("2022-01-03", periods=5, freq="B")
        bench_series = pd.Series([100.0, 101.0, 102.0, 103.0, 104.0], index=calendar)

        # Stock A has day 2 and day 3 missing (only days 0, 1, 4 present)
        stock_calendar = calendar[[0, 1, 4]]
        stock_series = pd.Series([50.0, 52.0, 55.0], index=stock_calendar)

        def mock_fetch_impl(ticker, *args, **kwargs):
            if "^NSEI" in ticker:
                return bench_series
            return stock_series

        mock_fetch.side_effect = mock_fetch_impl

        # Run download for NIFTY_IT on COVID_2020 using mock tmp_path
        out_path, rep = download_sector_regime(
            sector="NIFTY_IT",
            regime_key="COVID_2020",
            overwrite=True,
            delay=0,
        )

        assert out_path.exists()
        saved_df = pd.read_csv(out_path, index_col=0)

        # Verify that missing rows are NaN, not 0.0, and not forward-filled
        first_stock_col = saved_df.columns[0]
        assert saved_df[first_stock_col].isna().sum() == 2
        assert (saved_df[first_stock_col] == 0).sum() == 0


class TestRetryAndErrorHandling:
    """Tests verifying retry logic for transient errors and bypass for permanent errors."""

    @patch("scripts.download_historical_data.time.sleep")
    @patch("scripts.download_historical_data.yf.download")
    def test_transient_error_retries_and_succeeds(self, mock_yf, mock_sleep):
        """Transient errors should retry up to max_retries before succeeding."""
        df_good = pd.DataFrame({"Close": [100.0, 101.0]})
        # Fail twice with transient ConnectionError, then succeed on 3rd attempt
        mock_yf.side_effect = [
            ConnectionError("Temporary network reset"),
            TimeoutError("Request timed out"),
            df_good,
        ]

        res = fetch_ticker_data("TCS.NS", "2024-01-01", "2024-01-10", delay=0, max_retries=2, retry_delay=0)
        assert res is not None
        assert len(res) == 2
        assert mock_yf.call_count == 3

    @patch("scripts.download_historical_data.time.sleep")
    @patch("scripts.download_historical_data.yf.download")
    def test_permanent_404_error_does_not_retry(self, mock_yf, mock_sleep):
        """Permanent 404/not found errors should not be retried."""
        mock_yf.side_effect = Exception("HTTP Error 404: Quote not found for symbol: LTIM.NS")

        res = fetch_ticker_data("LTIM.NS", "2020-01-01", "2020-06-30", delay=0, max_retries=2)
        assert res is None
        # Must fail immediately on attempt 1 without calling yf.download 3 times
        assert mock_yf.call_count == 1


class TestBatchAndSafety:
    """Tests for batch execution error isolation and overwrite protection."""

    @patch("scripts.download_historical_data.download_sector_regime")
    def test_batch_continues_if_one_sector_fails(self, mock_download):
        """If one sector encounters an error, batch processing should continue for others."""
        def mock_impl(sector, *args, **kwargs):
            if sector == "NIFTY_IT":
                raise RuntimeError("Disk full on sector IT")
            return (None, {"status": "success", "sector": sector})

        mock_download.side_effect = mock_impl

        results = download_all_sectors_for_regime("COVID_2020", overwrite=False, delay=0)
        assert "NIFTY_IT" in results
        assert results["NIFTY_IT"]["status"] == "error"
        assert "NIFTY_BANK" in results
        assert results["NIFTY_BANK"]["status"] == "success"

    def test_overwrite_protection_skips_existing(self, tmp_path):
        """Existing file must be skipped when overwrite=False."""
        with patch("scripts.download_historical_data.DATA_DIR", tmp_path):
            existing_file = tmp_path / "NIFTY_IT__covid_2020.csv"
            existing_file.write_text("Date,TCS.NS,^NSEI\n2020-01-01,100,1000\n", encoding="utf-8")

            out_path, rep = download_sector_regime("NIFTY_IT", "COVID_2020", overwrite=False)
            assert rep["status"] == "skipped_existing"
            # Content must remain identical
            assert "2020-01-01,100,1000" in existing_file.read_text(encoding="utf-8")


class TestPhase1DatasetsIntegrity:
    """Verifies the integrity, schema, and non-corruption of all Phase 1 ingested datasets."""

    SECTORS = [
        "NIFTY_IT",
        "NIFTY_BANK",
        "NIFTY_AUTO",
        "NIFTY_PHARMA",
        "NIFTY_PSU_BANK",
        "NIFTY_PRIVATE_BANK",
    ]
    REGIMES = [
        "COVID_2020",
        "ELECTION_2024",
        "TECH_SELLOFF_2022",
        "2008_GFC",
    ]

    def test_all_24_historical_datasets_exist(self):
        """All 24 historical sector/regime combinations must exist on disk."""
        from pathlib import Path
        data_dir = Path("data")
        for s in self.SECTORS:
            for r in self.REGIMES:
                filename = f"{s}__{r.lower()}.csv"
                file_path = data_dir / filename
                assert file_path.exists(), f"Missing historical dataset: {filename}"
                assert file_path.stat().st_size > 0, f"File is empty: {filename}"

    def test_historical_datasets_schema_and_integrity(self):
        """Every historical dataset must adhere strictly to the StocX Data Contract."""
        from pathlib import Path
        data_dir = Path("data")
        for s in self.SECTORS:
            for r in self.REGIMES:
                filename = f"{s}__{r.lower()}.csv"
                file_path = data_dir / filename
                df = pd.read_csv(file_path)

                # Schema checks
                assert df.columns[0] == "Date", f"{filename}: Date is not the first column"
                assert df.columns[-1] == "^NSEI", f"{filename}: ^NSEI is not the last column"
                assert len(df.columns) == len(set(df.columns)), f"{filename}: Duplicate columns found"

                # Date ordering and format
                parsed_dates = pd.to_datetime(df["Date"], format="%Y-%m-%d", errors="coerce")
                assert parsed_dates.notna().all(), f"{filename}: Invalid date format"
                assert df["Date"].is_monotonic_increasing, f"{filename}: Dates not strictly ascending"
                assert df["Date"].is_unique, f"{filename}: Duplicate dates found"

                # Zero price prohibition
                for col in df.columns:
                    if col == "Date":
                        continue
                    series = pd.to_numeric(df[col], errors="coerce")
                    assert (series == 0).sum() == 0, f"{filename}: Artificial zero found in column {col}"

    def test_fundamentals_integrity(self):
        """Current fundamentals dataset must be properly structured with zero artificial zeroes."""
        from pathlib import Path
        fund_path = Path("data/fundamentals_2026-10-30.csv")
        assert fund_path.exists(), "Fundamentals CSV missing"
        df = pd.read_csv(fund_path)

        expected_cols = [
            "ticker", "company_name", "market_cap", "trailing_pe", "forward_pe",
            "return_on_equity", "revenue_growth", "debt_to_equity", "profit_margins",
            "sector", "industry"
        ]
        assert list(df.columns) == expected_cols
        assert df["ticker"].is_unique
        assert len(df) >= 51
        for col in ["trailing_pe", "forward_pe", "market_cap"]:
            assert (df[col] == 0).sum() == 0, f"Artificial zero found in {col}"

    def test_lot_sizes_integrity(self):
        """NSE lot sizes dataset must contain verified positive integer lots and correct metadata."""
        from pathlib import Path
        lot_path = Path("data/nse_lot_sizes.csv")
        assert lot_path.exists(), "NSE lot sizes CSV missing"
        df = pd.read_csv(lot_path)

        expected_cols = ["ticker", "symbol", "underlying_name", "lot_size", "expiry", "as_of_date"]
        assert list(df.columns) == expected_cols
        assert df["ticker"].is_unique
        assert len(df) == 46
        assert (df["lot_size"] <= 0).sum() == 0
        assert (df["expiry"] == "NOV-26").all()
        assert (df["as_of_date"] == "2026-10-30").all()

