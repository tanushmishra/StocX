"""
Historical Data Ingestion Module for StocX
Downloads real historical stock prices per the StocX Data Contract:
- Target path: data/<SECTOR>__<regime_lower>.csv
- Columns: Date, <Ticker 1>, ..., <Ticker N>, ^NSEI
- Aligned to active NSE trading sessions (derived from benchmark ^NSEI).
- No synthetic prices or zero-filling; missing prices remain NaN/blank.
- Regime-agnostic drawdown calculation.
- Rate limiting and retry handling.
- Overwrite protection.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import yfinance as yf

import config

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")


def compute_max_drawdown(series: pd.Series | None) -> dict[str, Any]:
    """Calculate maximum peak-to-trough drawdown for any regime window.

    Args:
        series: Price series with date index (strings or DatetimeIndex).

    Returns:
        dict with peak_value, peak_date, trough_value, trough_date,
        max_drawdown_pct, and crash_visible.
    """
    if series is None or len(series.dropna()) < 2:
        return {
            "pre_crash_peak": None,
            "peak_date": None,
            "crash_trough": None,
            "trough_date": None,
            "max_drawdown_pct": None,
            "crash_visible": False,
        }

    s = series.dropna()
    cummax = s.cummax()
    drawdown = (s - cummax) / cummax
    trough_idx = drawdown.idxmin()
    max_dd_pct = float(drawdown.loc[trough_idx] * 100.0)

    # Peak occurring on or before the trough date
    peak_idx = s.loc[:trough_idx].idxmax()

    def _format_date(d: Any) -> str:
        if isinstance(d, pd.Timestamp):
            return d.strftime("%Y-%m-%d")
        return str(d)

    return {
        "pre_crash_peak": float(s.loc[peak_idx]),
        "peak_date": _format_date(peak_idx),
        "crash_trough": float(s.loc[trough_idx]),
        "trough_date": _format_date(trough_idx),
        "max_drawdown_pct": round(max_dd_pct, 2),
        "crash_visible": bool(max_dd_pct <= -15.0),
    }


def fetch_ticker_data(
    ticker: str,
    start_date: str,
    end_date: str,
    cache: dict[tuple[str, str, str], pd.Series] | None = None,
    delay: float = 0.5,
    max_retries: int = 2,
    retry_delay: float = 1.0,
) -> pd.Series | None:
    """Download single ticker price series with memoization, rate-limiting, and retries.

    Args:
        ticker: Symbol string (e.g. 'TCS.NS', '^NSEI').
        start_date: Start date YYYY-MM-DD.
        end_date: End date YYYY-MM-DD (exclusive).
        cache: In-memory cache mapping (ticker, start, end) -> Series.
        delay: Seconds to sleep between network requests.
        max_retries: Number of retry attempts on transient network errors.
        retry_delay: Delay between retries in seconds.

    Returns:
        pd.Series of close prices or None if permanently unavailable.
    """
    cache_key = (ticker, start_date, end_date)
    if cache is not None and cache_key in cache:
        logger.debug("Cache hit for %s [%s -> %s]", ticker, start_date, end_date)
        return cache[cache_key]

    series: pd.Series | None = None
    permanent_error = False

    for attempt in range(max_retries + 1):
        try:
            raw = yf.download(
                ticker,
                start=start_date,
                end=end_date,
                auto_adjust=True,
                progress=False,
            )
            # Apply rate-limiting delay after network call
            if delay > 0:
                time.sleep(delay)

            if raw is None or raw.empty or len(raw) == 0:
                # Often empty means unquoted/delisted for this window
                permanent_error = True
                break

            if isinstance(raw.columns, pd.MultiIndex):
                c = raw["Close"].iloc[:, 0]
            elif "Close" in raw:
                c = raw["Close"]
            else:
                c = raw.iloc[:, 0]

            c.name = ticker
            series = c
            break

        except Exception as exc:
            err_msg = str(exc).lower()
            # Permanent errors: 404, not found, delisted
            if "404" in err_msg or "not found" in err_msg or "delisted" in err_msg:
                permanent_error = True
                logger.warning("%s encountered permanent error (%s); will not retry.", ticker, exc)
                break

            if attempt < max_retries:
                logger.warning("Transient error fetching %s (attempt %d/%d): %s. Retrying in %.1fs...",
                               ticker, attempt + 1, max_retries + 1, exc, retry_delay)
                time.sleep(retry_delay)
            else:
                logger.error("Final failure fetching %s after %d attempts: %s", ticker, max_retries + 1, exc)

    if series is not None and cache is not None:
        cache[cache_key] = series

    return series


def download_sector_regime(
    sector: str,
    regime_key: str,
    overwrite: bool = False,
    cache: dict[tuple[str, str, str], pd.Series] | None = None,
    delay: float = 0.5,
) -> tuple[Path, dict[str, Any]]:
    """Download historical adjusted close prices for a sector and crash regime.

    Adheres strictly to the StocX Data Contract:
    - Path: data/<SECTOR>__<regime_lower>.csv
    - Columns: Date, <Ticker 1>, ..., <Ticker N>, ^NSEI
    - Missing prices remain blank/NaN; no forward-filling, no zero-filling.
    - Overwrite protection: skips if exists and overwrite=False.

    Args:
        sector: Key in config.SECTOR_TICKERS (e.g. 'NIFTY_IT')
        regime_key: Key in config.CRASH_REGIMES (e.g. 'COVID_2020')
        overwrite: Whether to overwrite an existing CSV file.
        cache: Optional in-memory cache to share across multiple calls.
        delay: Rate limit delay in seconds.

    Returns:
        (saved_csv_path, report_dict)
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if sector not in config.SECTOR_TICKERS:
        raise ValueError(f"Unknown sector '{sector}'. Available: {list(config.SECTOR_TICKERS.keys())}")
    if regime_key not in config.CRASH_REGIMES:
        raise ValueError(f"Unknown regime '{regime_key}'. Available: {list(config.CRASH_REGIMES.keys())}")

    filename = f"{sector}__{regime_key.lower()}.csv"
    out_path = DATA_DIR / filename

    if out_path.exists() and not overwrite:
        logger.info("Dataset %s already exists and overwrite=False. Skipping download.", out_path)
        existing_df = pd.read_csv(out_path, index_col=0)
        return out_path, {
            "status": "skipped_existing",
            "file_path": str(out_path.resolve()),
            "file_relative": str(out_path),
            "sector": sector,
            "regime": regime_key,
            "row_count": len(existing_df),
            "columns": list(existing_df.columns),
            "note": "File exists. Pass overwrite=True to re-download.",
        }

    regime_info = config.CRASH_REGIMES[regime_key]
    start_date = regime_info["start"]
    end_date = regime_info["end"]
    benchmark = config.DEFAULT_BENCHMARK

    # In yfinance end date is exclusive; add 1 day so end_date is included
    end_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1)
    end_str = end_dt.strftime("%Y-%m-%d")

    tickers = list(config.SECTOR_TICKERS[sector])
    logger.info("Ingesting %s for %s (%s to %s)", sector, regime_key, start_date, end_date)

    # 1. Download benchmark first to obtain the official NSE trading calendar
    logger.info("Fetching benchmark %s...", benchmark)
    bench_series = fetch_ticker_data(benchmark, start_date, end_str, cache=cache, delay=delay)
    if bench_series is None or len(bench_series.dropna()) == 0:
        raise RuntimeError(f"Failed to fetch benchmark data for {benchmark} during {start_date} -> {end_date}")

    trading_calendar = bench_series.index
    logger.info("Benchmark trading sessions: %d days (%s to %s)",
                len(trading_calendar),
                trading_calendar.min().strftime("%Y-%m-%d"),
                trading_calendar.max().strftime("%Y-%m-%d"))

    # 2. Download each constituent ticker individually
    retained_series: dict[str, pd.Series] = {}
    failed_tickers: dict[str, str] = {}
    missing_observations: dict[str, int] = {}

    for ticker in tickers:
        logger.info("Fetching %s...", ticker)
        t_series = fetch_ticker_data(ticker, start_date, end_str, cache=cache, delay=delay)

        if t_series is None or len(t_series) == 0:
            failed_tickers[ticker] = "No data returned (symbol not active/listed for this period)"
            continue

        c = t_series.reindex(trading_calendar)
        valid_count = int(c.dropna().count())
        null_count = int(c.isnull().sum())

        if valid_count == 0:
            failed_tickers[ticker] = (
                "All values NaN (symbol unquoted/delisted during this period; "
                "no valid trading data available)"
            )
        elif valid_count < 10 and len(trading_calendar) > 30:
            failed_tickers[ticker] = f"Insufficient trading history ({valid_count} valid days out of {len(trading_calendar)})"
        else:
            if null_count > 0:
                logger.warning("%s has %d missing observations (preserved as NaN)", ticker, null_count)
                missing_observations[ticker] = null_count

            # PRESERVE MISSING PRICES AS NAN. DO NOT FORWARD FILL, DO NOT ZERO-FILL.
            retained_series[ticker] = c

    # Add benchmark as final column per contract
    retained_series[benchmark] = bench_series.reindex(trading_calendar)

    # 3. Assemble and align DataFrame
    df = pd.DataFrame(retained_series, index=trading_calendar)
    df.index.name = "Date"
    df.index = df.index.strftime("%Y-%m-%d")

    # 4. Save CSV with empty strings for missing observations (never zero)
    df.to_csv(out_path, index=True, na_rep="")
    logger.info("Saved %s (shape: %s)", out_path, df.shape)

    # 5. Regime-agnostic validation metrics
    drawdown_metrics = compute_max_drawdown(df[benchmark])

    report = {
        "status": "success",
        "file_path": str(out_path.resolve()),
        "file_relative": str(out_path),
        "sector": sector,
        "regime": regime_key,
        "row_count": len(df),
        "column_count": len(df.columns),
        "date_range": (df.index.min(), df.index.max()),
        "columns": list(df.columns),
        "null_counts": {col: int(df[col].isnull().sum()) for col in df.columns},
        "zero_counts": {col: int((df[col] == 0).sum()) for col in df.columns},
        "missing_observations": missing_observations,
        "failed_tickers": failed_tickers,
        "regime_drawdown_validation": drawdown_metrics,
    }

    return out_path, report


def download_all_sectors_for_regime(
    regime_key: str,
    overwrite: bool = False,
    delay: float = 0.5,
) -> dict[str, dict[str, Any]]:
    """Batch helper: Ingest all configured sectors for a given stress regime.

    Iterates through all sectors in config.SECTOR_TICKERS, logging individual
    results and continuing if one sector encounters an error.

    Args:
        regime_key: Key in config.CRASH_REGIMES (e.g. 'COVID_2020')
        overwrite: Whether to overwrite existing files.
        delay: Sleep delay between ticker requests.

    Returns:
        dict mapping sector_name -> report dict or error dict.
    """
    if regime_key not in config.CRASH_REGIMES:
        raise ValueError(f"Unknown regime '{regime_key}'. Available: {list(config.CRASH_REGIMES.keys())}")

    sectors = list(config.SECTOR_TICKERS.keys())
    logger.info("Beginning batch download for regime '%s' across %d sectors", regime_key, len(sectors))

    shared_cache: dict[tuple[str, str, str], pd.Series] = {}
    batch_results: dict[str, dict[str, Any]] = {}

    for idx, sector in enumerate(sectors, 1):
        logger.info("[%d/%d] Ingesting sector: %s for regime: %s", idx, len(sectors), sector, regime_key)
        try:
            _, report = download_sector_regime(
                sector=sector,
                regime_key=regime_key,
                overwrite=overwrite,
                cache=shared_cache,
                delay=delay,
            )
            batch_results[sector] = report
        except Exception as exc:
            logger.error("Failed downloading sector %s for regime %s: %s", sector, regime_key, exc)
            batch_results[sector] = {
                "status": "error",
                "sector": sector,
                "regime": regime_key,
                "error": str(exc),
            }

    logger.info("Batch download complete for regime '%s'. Successfully processed %d sectors.",
                regime_key, len(batch_results))
    return batch_results


if __name__ == "__main__":
    # Module entry point: safe inspection, does not run batch automatically
    print("Historical Data Ingestion Module loaded.")
    print("Available Sectors:", list(config.SECTOR_TICKERS.keys()))
    print("Available Regimes:", list(config.CRASH_REGIMES.keys()))
