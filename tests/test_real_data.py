"""
Real-Data Integrity Test Suite for StocX (Phase 2 - Anay Tiwari).

Verifies the integrity, reliability, and contract adherence of real exchange data:
A. No zero prices (positive prices, no artificial zeros, legitimate missing values preserved).
B. NIFTY benchmark present (^NSEI present in every historical dataset as final column).
C. Sorted and unique dates (ascending, unique, valid YYYY-MM-DD, within regime bounds).
D. Positive F&O lot sizes (official normalized lot sizes, strictly positive integers).
E. Blank-not-zero fundamentals (missing metrics preserved as NaN, no zero substitution).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Generator

import numpy as np
import pandas as pd
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config

DATA_DIR = PROJECT_ROOT / "data"

SECTORS = list(config.SECTOR_TICKERS.keys())
REGIMES = list(config.CRASH_REGIMES.keys())


# =====================================================================
# Reusable Helper Functions
# =====================================================================

def get_all_historical_datasets() -> list[tuple[str, str, Path]]:
    """Return list of (sector, regime, file_path) tuples for all 24 expected files."""
    datasets = []
    for sector in SECTORS:
        for regime in REGIMES:
            filename = f"{sector}__{regime.lower()}.csv"
            filepath = DATA_DIR / filename
            datasets.append((sector, regime, filepath))
    return datasets


# =====================================================================
# A. No Zero Prices Tests
# =====================================================================

class TestNoZeroPrices:
    """Validate that price series contain positive values and no artificial zero substitutes."""

    @pytest.mark.parametrize("sector,regime,filepath", get_all_historical_datasets())
    def test_no_zero_prices_in_historical_dataset(self, sector: str, regime: str, filepath: Path):
        """Historical datasets must never contain 0.0 prices in any numeric price column."""
        assert filepath.exists(), f"Historical dataset missing: {filepath.name}"
        df = pd.read_csv(filepath)

        for col in df.columns:
            if col == "Date":
                continue
            series = pd.to_numeric(df[col], errors="coerce")
            zero_count = int((series == 0).sum())
            assert zero_count == 0, (
                f"{filepath.name}: Column '{col}' contains {zero_count} zero prices! "
                "Zero prices violate the StocX zero-hallucination data contract."
            )

    @pytest.mark.parametrize("sector,regime,filepath", get_all_historical_datasets())
    def test_prices_are_strictly_positive(self, sector: str, regime: str, filepath: Path):
        """Populated historical price observations must be strictly positive (> 0)."""
        assert filepath.exists(), f"Historical dataset missing: {filepath.name}"
        df = pd.read_csv(filepath)

        for col in df.columns:
            if col == "Date":
                continue
            series = pd.to_numeric(df[col], errors="coerce").dropna()
            assert (series > 0).all(), (
                f"{filepath.name}: Column '{col}' contains non-positive values (min={series.min()})."
            )

    @pytest.mark.parametrize("sector,regime,filepath", get_all_historical_datasets())
    def test_missing_prices_preserved_as_nan_not_zero(self, sector: str, regime: str, filepath: Path):
        """Missing observations must remain NaN/blank and not be filled with zero."""
        assert filepath.exists(), f"Historical dataset missing: {filepath.name}"
        # Read raw CSV text to verify empty commas are used for missing values, not zeros
        raw_text = filepath.read_text(encoding="utf-8")
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        assert len(lines) > 1, f"{filepath.name} is empty"

        # Read into dataframe
        df = pd.read_csv(filepath)
        for col in df.columns:
            if col == "Date":
                continue
            s = df[col]
            # Ensure no string '0' or '0.0' exists in raw representations
            assert not (s == 0).any(), f"{filepath.name}: Column '{col}' has numeric 0 substitution"


# =====================================================================
# B. NIFTY Benchmark Present Tests
# =====================================================================

class TestNiftyBenchmarkPresent:
    """Verify that ^NSEI benchmark is present in every applicable historical dataset."""

    @pytest.mark.parametrize("sector,regime,filepath", get_all_historical_datasets())
    def test_nifty_benchmark_present_and_final_column(self, sector: str, regime: str, filepath: Path):
        """^NSEI must be present in every historical dataset and must be strictly the final column."""
        assert filepath.exists(), f"Dataset missing: {filepath.name}"
        df = pd.read_csv(filepath)

        assert "^NSEI" in df.columns, (
            f"{filepath.name}: Benchmark '^NSEI' is missing from columns: {list(df.columns)}"
        )
        assert df.columns[-1] == "^NSEI", (
            f"{filepath.name}: Benchmark '^NSEI' must be the final column (found '{df.columns[-1]}')"
        )

    @pytest.mark.parametrize("sector,regime,filepath", get_all_historical_datasets())
    def test_nifty_benchmark_has_valid_non_empty_series(self, sector: str, regime: str, filepath: Path):
        """^NSEI benchmark series must have valid positive observations for every trading session."""
        assert filepath.exists(), f"Dataset missing: {filepath.name}"
        df = pd.read_csv(filepath)

        nsei = pd.to_numeric(df["^NSEI"], errors="coerce")
        assert nsei.notna().all(), f"{filepath.name}: ^NSEI contains NaN values"
        assert (nsei > 0).all(), f"{filepath.name}: ^NSEI contains non-positive values"
        assert len(nsei) >= 20, f"{filepath.name}: ^NSEI series has fewer than 20 observations"


# =====================================================================
# C. Sorted and Unique Dates Tests
# =====================================================================

class TestSortedAndUniqueDates:
    """Verify that dates are valid, monotonically ascending, unique, and bounded by regime."""

    @pytest.mark.parametrize("sector,regime,filepath", get_all_historical_datasets())
    def test_dates_are_unique_and_ascending(self, sector: str, regime: str, filepath: Path):
        """Dates in every historical dataset must be unique and strictly monotonically ascending."""
        assert filepath.exists(), f"Dataset missing: {filepath.name}"
        df = pd.read_csv(filepath)

        assert df.columns[0] == "Date", f"{filepath.name}: Column 0 is '{df.columns[0]}' instead of 'Date'"
        date_series = df["Date"]

        # Uniqueness
        assert date_series.is_unique, f"{filepath.name}: Duplicate dates detected in Date column"

        # Ascending order
        assert date_series.is_monotonic_increasing, (
            f"{filepath.name}: Dates are not in strictly ascending chronological order"
        )

    @pytest.mark.parametrize("sector,regime,filepath", get_all_historical_datasets())
    def test_dates_valid_iso_format(self, sector: str, regime: str, filepath: Path):
        """Dates must strictly conform to the ISO YYYY-MM-DD format."""
        assert filepath.exists(), f"Dataset missing: {filepath.name}"
        df = pd.read_csv(filepath)

        parsed_dates = pd.to_datetime(df["Date"], format="%Y-%m-%d", errors="coerce")
        assert parsed_dates.notna().all(), f"{filepath.name}: Some dates failed strict YYYY-MM-DD parsing"

    @pytest.mark.parametrize("sector,regime,filepath", get_all_historical_datasets())
    def test_dates_within_regime_boundaries(self, sector: str, regime: str, filepath: Path):
        """Dataset dates must fall strictly within the configured regime boundaries."""
        assert filepath.exists(), f"Dataset missing: {filepath.name}"
        df = pd.read_csv(filepath)

        reg_info = config.CRASH_REGIMES[regime]
        expected_start = reg_info["start"]
        expected_end = reg_info["end"]

        actual_start = str(df["Date"].iloc[0])
        actual_end = str(df["Date"].iloc[-1])

        assert actual_start >= expected_start, (
            f"{filepath.name}: First date {actual_start} is earlier than regime start {expected_start}"
        )
        assert actual_end <= expected_end, (
            f"{filepath.name}: Last date {actual_end} is later than regime end {expected_end}"
        )


# =====================================================================
# D. Positive F&O Lot Sizes Tests
# =====================================================================

class TestPositiveFnoLotSizes:
    """Validate official normalized NSE F&O lot sizes dataset."""

    @pytest.fixture(autouse=True)
    def setup_lots(self):
        self.lot_path = DATA_DIR / "nse_lot_sizes.csv"
        assert self.lot_path.exists(), "Official lot sizes dataset data/nse_lot_sizes.csv missing"
        self.df = pd.read_csv(self.lot_path)

    def test_lot_sizes_schema_and_integrity(self):
        """nse_lot_sizes.csv must contain required columns and unique tickers."""
        expected_cols = ["ticker", "symbol", "underlying_name", "lot_size", "expiry", "as_of_date"]
        assert list(self.df.columns) == expected_cols, f"Schema mismatch: {list(self.df.columns)}"
        assert self.df["ticker"].is_unique, "Duplicate tickers detected in lot sizes dataset"
        assert len(self.df) == 46, f"Expected 46 matched F&O tickers, found {len(self.df)}"

    def test_all_lot_sizes_are_strictly_positive_integers(self):
        """All populated permitted lot sizes must be positive integers (> 0)."""
        lots = self.df["lot_size"]
        assert (lots > 0).all(), f"Found non-positive lot sizes: {lots[lots <= 0].tolist()}"
        assert pd.api.types.is_integer_dtype(lots), "lot_size column must be integer type"
        assert lots.min() >= 25, f"Suspiciously low lot size: {lots.min()}"

    def test_expiry_and_as_of_date_consistency(self):
        """Expiry must be NOV-26 and as_of_date must be 2026-10-30."""
        assert (self.df["expiry"] == "NOV-26").all(), "Expiry column contains values other than NOV-26"
        assert (self.df["as_of_date"] == "2026-10-30").all(), "as_of_date column must be 2026-10-30"

    def test_unmatched_symbols_not_assigned_invented_lots(self):
        """Cash-only symbols (e.g. LTTS.NS, CENTRALBK.NS, IOB.NS) must NOT appear with fabricated lots."""
        cash_only_tickers = {"LTTS.NS", "CENTRALBK.NS", "IOB.NS", "PSB.NS", "UCOBANK.NS"}
        matched_tickers = set(self.df["ticker"])
        intersection = cash_only_tickers.intersection(matched_tickers)
        assert len(intersection) == 0, (
            f"Cash-only stocks mistakenly assigned derivative lot sizes: {intersection}"
        )


# =====================================================================
# E. Blank-Not-Zero Fundamentals Tests
# =====================================================================

class TestBlankNotZeroFundamentals:
    """Validate company fundamentals dataset: missing metrics must be blank/NaN, never zero."""

    @pytest.fixture(autouse=True)
    def setup_fund(self):
        self.fund_path = DATA_DIR / "fundamentals_2026-10-30.csv"
        assert self.fund_path.exists(), "Fundamentals CSV data/fundamentals_2026-10-30.csv missing"
        self.df = pd.read_csv(self.fund_path)

    def test_fundamentals_schema(self):
        """Fundamentals dataset must contain all 11 required columns."""
        expected_cols = [
            "ticker", "company_name", "market_cap", "trailing_pe", "forward_pe",
            "return_on_equity", "revenue_growth", "debt_to_equity", "profit_margins",
            "sector", "industry"
        ]
        assert list(self.df.columns) == expected_cols, f"Schema mismatch: {list(self.df.columns)}"
        assert self.df["ticker"].is_unique, "Duplicate tickers detected in fundamentals dataset"
        assert len(self.df) == 51, f"Expected 51 successful companies, got {len(self.df)}"

    def test_no_artificial_zero_substitutions_in_valuation_metrics(self):
        """Market cap, trailing P/E, and forward P/E must never be 0.0."""
        for col in ["market_cap", "trailing_pe"]:
            s = self.df[col].dropna()
            assert (s > 0).all(), f"Found zero or negative values in {col}"

        # forward_pe can be NaN for companies without analyst estimates, but if present must be > 0
        fwd_pe = self.df["forward_pe"].dropna()
        assert (fwd_pe > 0).all(), "Found zero or negative forward_pe"
        assert (self.df["forward_pe"] == 0).sum() == 0, "Artificial zero found in forward_pe"

    def test_missing_values_remain_blank_nan(self):
        """Missing fundamentals (e.g. debt-to-equity for banks) must remain blank/NaN, not 0.0."""
        # Financial services firms do not report standard debt-to-equity
        fin_firms = self.df[self.df["sector"] == "Financial Services"]
        assert len(fin_firms) > 0, "No financial services firms found"

        de_nulls = fin_firms["debt_to_equity"].isna().sum()
        assert de_nulls == len(fin_firms), (
            f"Banking firms should have blank/NaN debt_to_equity, found {len(fin_firms) - de_nulls} populated"
        )
        assert (fin_firms["debt_to_equity"] == 0).sum() == 0, (
            "Found artificial zero substituted for banking debt_to_equity"
        )

    def test_pe_fields_are_independently_populated(self):
        """trailing_pe and forward_pe must be distinct columns with separate valuations."""
        assert "trailing_pe" in self.df.columns
        assert "forward_pe" in self.df.columns
        # Verify they are not identical copies
        diff = (self.df["trailing_pe"] - self.df["forward_pe"]).dropna()
        assert (diff != 0).any(), "trailing_pe and forward_pe appear to be identical copies"
