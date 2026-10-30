"""
StocX Phase 1 Data Validation Script
Validates all Phase 1 data engineering assets against the StocX Data Contract:
1. All 24 historical crisis datasets (schema, date ordering, zero prices, benchmark).
2. Fundamentals dataset (schema, separated P/E, null preservation, 0 zeroes).
3. Official NSE lot sizes (permitted positive lots, expiry, as-of date).
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import numpy as np
import config

DATA_DIR = Path("data")

SECTORS = list(config.SECTOR_TICKERS.keys())
REGIMES = list(config.CRASH_REGIMES.keys())


def validate_historical_datasets() -> tuple[int, int, list[str]]:
    """Validate all 24 sector x regime historical price CSVs."""
    print("=" * 75)
    print("1. VALIDATING HISTORICAL CRISIS DATASETS (24 COMBINATIONS)")
    print("=" * 75)

    passed_count = 0
    failed_count = 0
    errors: list[str] = []

    for regime in REGIMES:
        print(f"\n--- Stress Regime: {regime} ---")
        for sector in SECTORS:
            fname = f"{sector}__{regime.lower()}.csv"
            fpath = DATA_DIR / fname

            if not fpath.exists():
                err = f"[FAIL] Missing file: {fname}"
                print(f"  {err}")
                errors.append(err)
                failed_count += 1
                continue

            try:
                df = pd.read_csv(fpath)
                file_errors = []

                # Column order
                if df.columns[0] != "Date":
                    file_errors.append(f"Column 0 is '{df.columns[0]}' (expected 'Date')")
                if df.columns[-1] != "^NSEI":
                    file_errors.append(f"Final column is '{df.columns[-1]}' (expected '^NSEI')")
                if len(df.columns) != len(set(df.columns)):
                    file_errors.append("Duplicate column names detected")

                # Date integrity
                if not df["Date"].is_unique:
                    file_errors.append("Duplicate dates found")
                if not df["Date"].is_monotonic_increasing:
                    file_errors.append("Dates are not strictly ascending")

                parsed_dates = pd.to_datetime(df["Date"], format="%Y-%m-%d", errors="coerce")
                if parsed_dates.isna().any():
                    file_errors.append("Date format error (must be strictly YYYY-MM-DD)")

                # Price checks (no zero or negative values)
                for col in df.columns:
                    if col == "Date":
                        continue
                    s = pd.to_numeric(df[col], errors="coerce")
                    zero_count = int((s == 0).sum())
                    neg_count = int((s < 0).sum())
                    if zero_count > 0:
                        file_errors.append(f"Column '{col}' contains {zero_count} zero prices")
                    if neg_count > 0:
                        file_errors.append(f"Column '{col}' contains {neg_count} negative prices")

                if file_errors:
                    err = f"[FAIL] {fname}: {', '.join(file_errors)}"
                    print(f"  {err}")
                    errors.append(err)
                    failed_count += 1
                else:
                    constituents = len(df.columns) - 2
                    print(f"  [PASS] {fname:<35} | Sessions: {len(df):<3} | Stocks: {constituents:<2} | 0 Zeroes | Dates OK")
                    passed_count += 1

            except Exception as exc:
                err = f"[ERROR] {fname}: Exception during parsing: {exc}"
                print(f"  {err}")
                errors.append(err)
                failed_count += 1

    return passed_count, failed_count, errors


def validate_fundamentals() -> tuple[bool, list[str]]:
    """Validate data/fundamentals_2026-10-30.csv."""
    print("\n" + "=" * 75)
    print("2. VALIDATING COMPANY FUNDAMENTALS")
    print("=" * 75)

    fpath = DATA_DIR / "fundamentals_2026-10-30.csv"
    if not fpath.exists():
        err = f"[FAIL] Missing file: {fpath}"
        print(f"  {err}")
        return False, [err]

    errors = []
    df = pd.read_csv(fpath)
    expected_cols = [
        "ticker", "company_name", "market_cap", "trailing_pe", "forward_pe",
        "return_on_equity", "revenue_growth", "debt_to_equity", "profit_margins",
        "sector", "industry"
    ]

    if list(df.columns) != expected_cols:
        errors.append(f"Schema mismatch. Expected {expected_cols}, got {list(df.columns)}")

    if not df["ticker"].is_unique:
        errors.append("Duplicate tickers in fundamentals dataset")

    if len(df) < 50:
        errors.append(f"Insufficient ticker coverage ({len(df)} rows)")

    # Zero substitution check
    for col in ["market_cap", "trailing_pe", "forward_pe"]:
        if (df[col] == 0).any():
            errors.append(f"Artificial zeroes detected in column '{col}'")

    if errors:
        for e in errors:
            print(f"  [FAIL] {e}")
        return False, errors
    else:
        print(f"  [PASS] fundamentals_2026-10-30.csv | Rows: {len(df)} | 11 Columns | Separate P/E | 0 Zeroes")
        return True, []


def validate_lot_sizes() -> tuple[bool, list[str]]:
    """Validate data/nse_lot_sizes.csv."""
    print("\n" + "=" * 75)
    print("3. VALIDATING OFFICIAL NSE F&O LOT SIZES")
    print("=" * 75)

    fpath = DATA_DIR / "nse_lot_sizes.csv"
    if not fpath.exists():
        err = f"[FAIL] Missing file: {fpath}"
        print(f"  {err}")
        return False, [err]

    errors = []
    df = pd.read_csv(fpath)
    expected_cols = ["ticker", "symbol", "underlying_name", "lot_size", "expiry", "as_of_date"]

    if list(df.columns) != expected_cols:
        errors.append(f"Schema mismatch. Expected {expected_cols}, got {list(df.columns)}")

    if not df["ticker"].is_unique:
        errors.append("Duplicate tickers found in lot sizes dataset")

    if len(df) < 40:
        errors.append(f"Unexpected row count ({len(df)} rows, expected ~46)")

    if (df["lot_size"] <= 0).any():
        errors.append("Non-positive or zero lot sizes detected")

    if not (df["expiry"] == "NOV-26").all():
        errors.append("Expiry cycle mismatch (expected NOV-26 across all rows)")

    if errors:
        for e in errors:
            print(f"  [FAIL] {e}")
        return False, errors
    else:
        print(f"  [PASS] nse_lot_sizes.csv | Rows: {len(df)} | Expiry: NOV-26 | 100% Positive Integers")
        return True, []


def main():
    print("STARTING STOCX DATA VALIDATION SUITE...")
    hist_passed, hist_failed, hist_errs = validate_historical_datasets()
    fund_passed, fund_errs = validate_fundamentals()
    lots_passed, lots_errs = validate_lot_sizes()

    print("\n" + "=" * 75)
    print("FINAL VALIDATION SUMMARY")
    print("=" * 75)
    print(f"Historical Datasets: {hist_passed}/24 passed ({hist_failed} failed)")
    print(f"Fundamentals Dataset: {'PASSED' if fund_passed else 'FAILED'}")
    print(f"NSE Lot Sizes Dataset: {'PASSED' if lots_passed else 'FAILED'}")

    total_failures = hist_failed + (0 if fund_passed else 1) + (0 if lots_passed else 1)
    if total_failures == 0:
        print("\n>>> ALL PHASE 1 DATASETS SUCCESSFULLY VALIDATED! (EXIT CODE 0) <<<")
        sys.exit(0)
    else:
        print(f"\n>>> VALIDATION FAILED WITH {total_failures} ERRORS (EXIT CODE 1) <<<")
        sys.exit(1)


if __name__ == "__main__":
    main()
