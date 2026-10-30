"""
Download real NSE market data using yfinance and validate all sector files.

Sectors: NIFTY_IT, NIFTY_BANK, NIFTY_AUTO, NIFTY_PHARMA
Benchmark: ^NSEI

Windows:
  main_3y:       2023-10-01 to 2026-10-30
  gfc_2008:      2007-06-01 to 2009-06-30
  covid_2020:    2019-06-01 to 2020-12-31
  tech_2022:     2021-06-01 to 2022-12-31
  election_2024: 2023-10-01 to 2024-09-30
"""

import os
import sys
import time
from pathlib import Path
import pandas as pd
import numpy as np
import yfinance as yf

# Directories
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_CACHE_DIR = PROJECT_ROOT / "data_cache"
SCRATCH_DIR = PROJECT_ROOT / "scratch_data"
RAW_DIR = SCRATCH_DIR / "raw"

SCRATCH_DIR.mkdir(parents=True, exist_ok=True)
RAW_DIR.mkdir(parents=True, exist_ok=True)

# Sector constituents from config
SECTORS = {
    "NIFTY_IT": [
        "TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "TECHM.NS",
        "LTIM.NS", "MPHASIS.NS", "COFORGE.NS", "PERSISTENT.NS", "LTTS.NS",
    ],
    "NIFTY_BANK": [
        "HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS", "AXISBANK.NS",
        "SBIN.NS", "BANKBARODA.NS", "PNB.NS", "INDUSINDBK.NS",
        "BANDHANBNK.NS", "FEDERALBNK.NS", "IDFCFIRSTB.NS", "AUBANK.NS",
    ],
    "NIFTY_AUTO": [
        "MARUTI.NS", "M&M.NS", "TATAMOTORS.NS", "BAJAJ-AUTO.NS",
        "HEROMOTOCO.NS", "EICHERMOT.NS", "ASHOKLEY.NS", "TVSMOTOR.NS",
        "BALKRISIND.NS", "BHARATFORG.NS",
    ],
    "NIFTY_PHARMA": [
        "SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS",
        "APOLLOHOSP.NS", "AUROPHARMA.NS", "BIOCON.NS", "LUPIN.NS",
        "TORNTPHARM.NS", "ALKEM.NS",
    ],
}

BENCHMARK = "^NSEI"

WINDOWS = {
    "main_3y": {"start": "2023-10-01", "end": "2026-10-30", "yf_end": "2026-10-31"},
    "gfc_2008": {"start": "2007-06-01", "end": "2009-06-30", "yf_end": "2009-07-01"},
    "covid_2020": {"start": "2019-06-01", "end": "2020-12-31", "yf_end": "2021-01-01"},
    "tech_2022": {"start": "2021-06-01", "end": "2022-12-31", "yf_end": "2023-01-01"},
    "election_2024": {"start": "2023-10-01", "end": "2024-09-30", "yf_end": "2024-10-01"},
}


def download_single_ticker(ticker: str, start: str, yf_end: str, end: str) -> pd.Series:
    """Download close price for a single ticker with raw caching and retries."""
    safe_ticker = ticker.replace("^", "").replace(".", "_")
    raw_file = RAW_DIR / f"{safe_ticker}_{start}_{end}.csv"

    if raw_file.exists():
        df = pd.read_csv(raw_file, index_col=0, parse_dates=True)
        if "Close" in df.columns and len(df) > 0:
            s = df["Close"]
            s.name = ticker
            return s

    max_retries = 4
    for attempt in range(max_retries):
        try:
            raw = yf.download(
                ticker,
                start=start,
                end=yf_end,
                auto_adjust=True,
                progress=False,
            )
            time.sleep(1.0)  # Rule: Sleep 1 second between downloads

            if raw is not None and not raw.empty:
                # Handle MultiIndex if present
                if isinstance(raw.columns, pd.MultiIndex):
                    if ticker in raw["Close"].columns:
                        close_series = raw["Close"][ticker]
                    else:
                        close_series = raw["Close"].iloc[:, 0]
                elif "Close" in raw.columns:
                    close_series = raw["Close"]
                else:
                    close_series = raw.iloc[:, 0]

                close_series.name = ticker
                close_series = close_series.dropna()
                # Filter to target bounds
                close_series = close_series.loc[(close_series.index >= start) & (close_series.index <= end)]

                if len(close_series) > 0:
                    # Save raw cache
                    pd.DataFrame({"Close": close_series}).to_csv(raw_file)
                    return close_series
            
            # If empty, retry after backoff
            print(f"  [Empty/Retry {attempt+1}/{max_retries}] {ticker} for {start} to {end}")
            time.sleep(2.0 * (attempt + 1))
        except Exception as e:
            print(f"  [Error/Retry {attempt+1}/{max_retries}] {ticker} failed: {e}")
            time.sleep(2.0 * (attempt + 1))

    print(f"  [FAILED/CONFIRMED_EMPTY] {ticker} returned no data for {start} to {end}")
    return pd.Series(dtype=float, name=ticker)


def build_sector_file(sector_name: str, window_name: str, win_cfg: dict) -> tuple[Path, list[str]]:
    """Build and save <SECTOR>__<WINDOW>.csv according to download rules."""
    start = win_cfg["start"]
    end = win_cfg["end"]
    yf_end = win_cfg["yf_end"]

    # Target output file
    target_cache_file = DATA_CACHE_DIR / f"{sector_name}__{window_name}.csv"
    if target_cache_file.exists():
        print(f"Using existing data_cache file: {target_cache_file.name}")
        return target_cache_file, []

    output_file = SCRATCH_DIR / f"{sector_name}__{window_name}.csv"
    if output_file.exists():
        print(f"Using existing scratch file: {output_file.name}")
        # Check dropped tickers
        return output_file, []

    print(f"\nBuilding {sector_name}__{window_name}.csv ({start} to {end})...")

    # 1. Download benchmark first
    bench_series = download_single_ticker(BENCHMARK, start, yf_end, end)
    if bench_series.empty:
        raise RuntimeError(f"Benchmark {BENCHMARK} empty for window {window_name}")

    bench_dates = bench_series.index.sort_values().unique()
    total_market_days = len(bench_dates)

    combined_dict = {BENCHMARK: bench_series}
    dropped_tickers = []

    # 2. Download each constituent
    for ticker in SECTORS[sector_name]:
        stock_series = download_single_ticker(ticker, start, yf_end, end)
        if stock_series.empty:
            dropped_tickers.append(f"{ticker} (no data)")
            continue

        # Reindex to benchmark calendar
        reindexed = stock_series.reindex(bench_dates)
        missing_count = reindexed.isna().sum()
        missing_pct = missing_count / total_market_days

        if missing_pct > 0.05:
            dropped_tickers.append(f"{ticker} ({missing_pct:.1%} missing > 5%)")
        else:
            # Forward-fill gaps of at most 3 days
            filled = reindexed.ffill(limit=3)
            combined_dict[ticker] = filled

    # 3. Create DataFrame and dropna across all kept columns
    df = pd.DataFrame(combined_dict, index=bench_dates)
    df = df.dropna()

    # Reorder columns: Date first, then ^NSEI, then sorted tickers
    stock_cols = sorted([c for c in df.columns if c != BENCHMARK])
    cols_order = [BENCHMARK] + stock_cols
    df = df[cols_order]

    # Format Date column
    df.index.name = "Date"
    df_out = df.reset_index()
    df_out["Date"] = df_out["Date"].dt.strftime("%Y-%m-%d")
    df_out = df_out.sort_values("Date", ascending=True)

    df_out.to_csv(output_file, index=False)
    print(f"Saved {output_file.name}: {len(df_out)} rows, {len(stock_cols)} stocks + benchmark.")
    if dropped_tickers:
        print(f"  Dropped tickers: {', '.join(dropped_tickers)}")

    return output_file, dropped_tickers


def validate_file(file_path: Path) -> dict:
    """Validate according to Task 1 Step 5 rules."""
    df = pd.read_csv(file_path)

    # 1. First column Date
    has_date_col = df.columns[0] == "Date"

    # 2. ^NSEI present
    has_bench = BENCHMARK in df.columns

    # 3. Dates sorted and unique
    dates = pd.to_datetime(df["Date"])
    is_sorted = dates.is_monotonic_increasing
    is_unique = dates.is_unique

    # 4. No gaps > 7 calendar days
    date_diffs = dates.diff().dropna()
    max_gap_days = date_diffs.max().days if len(date_diffs) > 0 else 0
    no_gap_gt_7 = max_gap_days <= 7

    # 5. Row count >= 100
    row_count = len(df)
    has_min_rows = row_count >= 100

    # 6. No zero, negative, or NaN in price columns
    price_cols = [c for c in df.columns if c != "Date"]
    has_nan = df[price_cols].isna().any().any()
    has_zero_or_neg = (df[price_cols] <= 0).any().any()

    passed = (
        has_date_col and has_bench and is_sorted and is_unique
        and no_gap_gt_7 and has_min_rows and (not has_nan) and (not has_zero_or_neg)
    )

    result = {
        "file": file_path.name,
        "rows": row_count,
        "stocks": len(price_cols) - 1,
        "benchmark_present": has_bench,
        "sorted_unique": is_sorted and is_unique,
        "max_gap_days": max_gap_days,
        "no_nan": not has_nan,
        "no_zero_neg": not has_zero_or_neg,
        "passed": passed,
    }
    return result


def main():
    print("=" * 80)
    print("TASK 1: DOWNLOADING REAL DATA AND RUNNING VALIDATION SUITE")
    print("=" * 80)

    all_dropped = {}
    validation_results = []
    lowest_nsei_covid = None

    for window_name, win_cfg in WINDOWS.items():
        all_dropped[window_name] = {}
        for sector_name in SECTORS:
            file_path, dropped = build_sector_file(sector_name, window_name, win_cfg)
            all_dropped[window_name][sector_name] = dropped
            val = validate_file(file_path)
            validation_results.append(val)

            # Check COVID 2020 lowest close
            if window_name == "covid_2020" and lowest_nsei_covid is None:
                df_covid = pd.read_csv(file_path)
                if BENCHMARK in df_covid.columns:
                    min_idx = df_covid[BENCHMARK].idxmin()
                    lowest_nsei_covid = (df_covid.loc[min_idx, "Date"], df_covid.loc[min_idx, BENCHMARK])

    # Print Validation Table
    print("\n" + "=" * 80)
    print("DATA VALIDATION REPORT (PASS/FAIL)")
    print("=" * 80)
    print(f"{'File Name':<35} | {'Rows':<6} | {'Stocks':<6} | {'MaxGap':<6} | {'Status':<6}")
    print("-" * 75)
    for res in validation_results:
        status = "PASS" if res["passed"] else "FAIL"
        print(f"{res['file']:<35} | {res['rows']:<6} | {res['stocks']:<6} | {res['max_gap_days']:<4}d | {status:<6}")

    # Print Lowest ^NSEI close in COVID 2020
    if lowest_nsei_covid:
        print("\n" + "-" * 80)
        print(f"Lowest ^NSEI close in covid_2020 file: Date = {lowest_nsei_covid[0]}, Price = {lowest_nsei_covid[1]:.2f}")
        print("-" * 80)

    # Print Dropped Tickers
    print("\n" + "=" * 80)
    print("TICKERS DROPPED PER WINDOW (>5% missing data in window):")
    print("=" * 80)
    for win, sectors_dict in all_dropped.items():
        print(f"\nWindow: {win}")
        for sec, dropped in sectors_dict.items():
            if dropped:
                print(f"  {sec}: {', '.join(dropped)}")
            else:
                print(f"  {sec}: None (all constituents retained)")


if __name__ == "__main__":
    main()
