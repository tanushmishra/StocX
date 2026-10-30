"""Data fetching and caching module for the Market-Neutral Hedge Builder.

Provides functions to fetch historical price data, sector constituents,
fundamental data from CSV, and official NSE F&O lot sizes from CSV.

Implements cache-first behavior:
1. Valid cached market data is prioritized from ``data_cache/`` and ``data/``.
2. On cache miss, live market data is fetched via ``yfinance`` and cached.
3. If live fetch fails, synthetic fallback is permitted ONLY if ``ALLOW_SYNTHETIC=true``;
   otherwise a clear descriptive exception is raised.
4. Synthetic prices are NEVER saved to disk cache.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
try:
    import yfinance as yf
except ImportError:
    yf = None

import config

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants & Directory Paths
# ---------------------------------------------------------------------------

_CACHE_DIR = Path("data_cache")
_DATA_DIR = Path("data")

_DEFAULT_FUNDAMENTALS_CSV = _DATA_DIR / "fundamentals.csv"
_FALLBACK_FUNDAMENTALS_CSV = _DATA_DIR / "fundamentals_2026-10-30.csv"
_DEFAULT_LOT_SIZES_CSV = _DATA_DIR / "nse_lot_sizes.csv"

# Hard-coded NIFTY sectoral index constituents (Yahoo Finance NSE suffix).
_SECTOR_CONSTITUENTS: dict[str, list[str]] = {
    "NIFTY_IT": [
        "TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS", "TECHM.NS",
        "LTIM.NS", "MPHASIS.NS", "COFORGE.NS", "PERSISTENT.NS", "LTTS.NS",
    ],
    "NIFTY_BANK": [
        "HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS", "AXISBANK.NS",
        "SBIN.NS", "BANKBARODA.NS", "INDUSINDBK.NS", "PNB.NS",
        "FEDERALBNK.NS", "IDFCFIRSTB.NS", "BANDHANBNK.NS", "AUBANK.NS",
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
    "NIFTY_PSU_BANK": [
        "SBIN.NS", "BANKBARODA.NS", "PNB.NS", "CANBK.NS",
        "UNIONBANK.NS", "IOB.NS", "INDIANB.NS", "CENTRALBK.NS",
        "BANKINDIA.NS", "MAHABANK.NS",
    ],
}


# ---------------------------------------------------------------------------
# Public helpers & Configuration
# ---------------------------------------------------------------------------


def is_synthetic_allowed() -> bool:
    """Return whether synthetic price simulation is permitted as a fallback."""
    env_val = os.getenv("ALLOW_SYNTHETIC")
    if env_val is not None:
        return env_val.strip().lower() in ("true", "1", "yes")
    return getattr(config, "ALLOW_SYNTHETIC", False)


def _cache_path(label: str, start: str, end: str) -> Path:
    """Build a deterministic cache filename inside ``data_cache/``.

    Args:
        label: Descriptive label (e.g. ticker or group name).
        start: Start date string (YYYY-MM-DD).
        end: End date string (YYYY-MM-DD).

    Returns:
        A ``Path`` object pointing to the cache CSV.
    """
    safe_label = label.replace(" ", "_").replace("/", "_")
    return _CACHE_DIR / f"{safe_label}_{start}_{end}.csv"


def get_data_source(df: pd.DataFrame) -> str:
    """Return the data provenance string for a price DataFrame.

    Returns:
        ``"yfinance"``, ``"cache"``, or ``"synthetic_fallback"``.
    """
    return getattr(df, "attrs", {}).get("data_source", "yfinance")


def validate_cached_dataframe(df: pd.DataFrame) -> bool:
    """Validate that a cached price DataFrame meets integrity requirements.

    Checks:
    - Must be a non-empty DataFrame with at least 2 rows and 1 column.
    - Index must be parseable as datetime.
    - Numeric values only; cannot be all NaN.
    - Prices must be positive (> 0).
    - Series must not be completely flat (zero variance) across >= 10 rows.
    """
    if not isinstance(df, pd.DataFrame) or df.empty:
        return False
    if len(df) < 2 or len(df.columns) < 1:
        return False

    # Check index is DatetimeIndex or convertible
    if not isinstance(df.index, pd.DatetimeIndex):
        try:
            pd.to_datetime(df.index)
        except Exception:
            return False

    for col in df.columns:
        series = pd.to_numeric(df[col], errors="coerce").dropna()
        if series.empty:
            return False
        if (series <= 0).any():
            return False
        if len(series) >= 10 and float(series.std()) == 0.0:
            return False

    return True


def audit_cache_directory(cache_dir: Path | str | None = None) -> dict[str, Any]:
    """Audit the local CSV cache directory for file validity and data integrity.

    Returns:
        A dictionary with audit stats: total_files, valid_files, invalid_files (list),
        and details per file.
    """
    target_dir = Path(cache_dir) if cache_dir is not None else _CACHE_DIR
    if not target_dir.exists():
        return {
            "cache_dir": str(target_dir),
            "total_files": 0,
            "valid_files": 0,
            "invalid_files": [],
        }

    csv_files = list(target_dir.glob("*.csv"))
    valid_count = 0
    invalid_files = []

    for file_path in csv_files:
        try:
            df = pd.read_csv(file_path, index_col=0, parse_dates=True)
            if validate_cached_dataframe(df):
                valid_count += 1
            else:
                invalid_files.append({"file": file_path.name, "reason": "Failed integrity check"})
        except Exception as exc:
            invalid_files.append({"file": file_path.name, "reason": str(exc)})

    return {
        "cache_dir": str(target_dir),
        "total_files": len(csv_files),
        "valid_files": valid_count,
        "invalid_files": invalid_files,
    }


def _find_cached_prices(tickers: list[str], start: str, end: str) -> pd.DataFrame | None:
    """Search for valid cached price data in data_cache/ and data/."""
    # 1. Exact cache file match in data_cache/
    cache_label = "_".join(sorted(tickers))
    exact_file = _cache_path(cache_label, start, end)
    if exact_file.exists():
        logger.info("Exact cache hit candidate: %s", exact_file)
        try:
            df = pd.read_csv(exact_file, index_col=0, parse_dates=True)
            if validate_cached_dataframe(df):
                present = [t for t in tickers if t in df.columns]
                if len(present) == len(tickers):
                    cached_df = df[tickers].copy()
                    cached_df.attrs["data_source"] = "cache"
                    cached_df.attrs["is_synthetic"] = False
                    return cached_df
        except Exception as exc:
            logger.warning("Failed reading cache file %s: %s", exact_file, exc)

    # 2. Search data/ and data_cache/ for datasets covering all requested tickers
    search_dirs = [_CACHE_DIR, _DATA_DIR]
    start_ts = pd.to_datetime(start)
    end_ts = pd.to_datetime(end)

    for s_dir in search_dirs:
        if not s_dir.exists():
            continue
        for csv_file in s_dir.glob("*.csv"):
            if csv_file == exact_file:
                continue
            try:
                # Fast column check
                header_df = pd.read_csv(csv_file, index_col=0, nrows=1)
                if all(t in header_df.columns for t in tickers):
                    full_df = pd.read_csv(csv_file, index_col=0, parse_dates=True)
                    mask = (full_df.index >= start_ts) & (full_df.index <= end_ts)
                    sliced = full_df.loc[mask, tickers].dropna(how="all")
                    req_span = (end_ts - start_ts).total_seconds()
                    actual_span = (sliced.index[-1] - sliced.index[0]).total_seconds() if len(sliced) >= 2 else 0
                    is_span_sufficient = (actual_span >= req_span * 0.75) if req_span > 86400 * 30 else (len(sliced) >= 2)

                    if len(sliced) >= 2 and is_span_sufficient and validate_cached_dataframe(sliced):
                        logger.info("Matched valid cached dataset in %s (%d rows)", csv_file, len(sliced))
                        sliced.attrs["data_source"] = "cache"
                        sliced.attrs["is_synthetic"] = False
                        return sliced
            except Exception:
                continue

    return None


# ---------------------------------------------------------------------------
# Core API
# ---------------------------------------------------------------------------


def fetch_prices(
    tickers: list[str],
    start: str | None = None,
    end: str | None = None,
    lookback_days: int | None = None,
    allow_synthetic: bool | None = None,
) -> pd.DataFrame:
    """Fetch adjusted close prices for *tickers* between *start* and *end*.

    Data is first looked up in the local CSV cache (``data_cache/`` and ``data/``).
    On a cache hit, data is flagged with provenance ``data_source='cache'``.
    On a cache miss, data is downloaded via ``yfinance``, marked as
    ``data_source='yfinance'``, and persisted to disk in ``data_cache/``.

    If yfinance is offline or download fails:
    - If ``ALLOW_SYNTHETIC=false`` (default): raises RuntimeError.
    - If ``ALLOW_SYNTHETIC=true``: returns deterministic synthetic price series
      with ``data_source='synthetic_fallback'``. Synthetic data is NEVER
      saved to ``data_cache/``.

    Args:
        tickers: List of Yahoo Finance ticker symbols (e.g.
            ``["TCS.NS", "INFY.NS"]``).
        start: Start date in ``YYYY-MM-DD`` format.
        end: End date in ``YYYY-MM-DD`` format.
        lookback_days: Optional trailing calendar days if start/end omitted.
        allow_synthetic: Explicit override for synthetic fallback permission.
            If None, evaluates ``ALLOW_SYNTHETIC`` from environment / config.

    Returns:
        A ``pd.DataFrame`` with a ``DatetimeIndex`` and one column per
        ticker containing adjusted close prices. The DataFrame's ``.attrs``
        dictionary contains ``data_source`` and ``is_synthetic`` flags.

    Raises:
        ValueError: If tickers list is empty.
        RuntimeError: If data cannot be fetched and synthetic data is disallowed.
    """
    if not tickers:
        raise ValueError("tickers list must not be empty.")

    # Resolve dates
    today = datetime.now()
    if end is None:
        end = today.strftime("%Y-%m-%d")
    if start is None:
        days = lookback_days if lookback_days is not None else 365
        start_dt = today - pd.Timedelta(days=days)
        start = start_dt.strftime("%Y-%m-%d")

    _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # ── 1. Cache-first lookup ──────────────────────────────────────────
    cached_df = _find_cached_prices(tickers, start, end)
    if cached_df is not None:
        logger.info("Using cached market data for %s [%s → %s]", tickers, start, end)
        return cached_df

    # ── 2. Live market data download ───────────────────────────────────
    logger.info("Cache miss. Fetching live prices for %s [%s → %s] via yfinance", tickers, start, end)
    df = pd.DataFrame()
    data_source = "yfinance"
    is_synthetic = False

    if yf is not None:
        try:
            raw = yf.download(
                tickers,
                start=start,
                end=end,
                auto_adjust=True,
                progress=False,
                threads=True,
            )
            if isinstance(raw.columns, pd.MultiIndex):
                df = raw["Close"].copy()
            else:
                df = raw[["Close"]].copy()
                df.columns = tickers[:1]
        except Exception as exc:
            logger.warning("yfinance download failed (%s).", exc)

    # ── 3. Handle download failure / missing data ──────────────────────
    if df.empty or df.dropna(how="all").empty:
        synthetic_permitted = (
            allow_synthetic if allow_synthetic is not None else is_synthetic_allowed()
        )

        if not synthetic_permitted:
            raise RuntimeError(
                f"Live market data fetch failed for {tickers} [{start} → {end}] "
                f"and ALLOW_SYNTHETIC=false. Genuine cached or live data is required."
            )

        logger.warning(
            "Live yfinance data unavailable for %s [%s → %s]. "
            "Falling back to synthetic price simulation per ALLOW_SYNTHETIC=true.",
            tickers, start, end,
        )
        data_source = "synthetic_fallback"
        is_synthetic = True

        dates = pd.date_range(start=start, end=end, freq="B")
        if len(dates) == 0:
            dates = pd.date_range(end=today, periods=252, freq="B")

        cache_label = "_".join(sorted(tickers))
        rng = np.random.default_rng(seed=abs(hash(cache_label)) % (2**32))
        data = {}
        for ticker in tickers:
            base_price = 1000.0 if "NIFTY" not in ticker else 15000.0
            drift = 0.0004
            vol = 0.015
            shocks = rng.normal(drift, vol, len(dates))
            prices_series = base_price * np.exp(np.cumsum(shocks))
            data[ticker] = prices_series
        df = pd.DataFrame(data, index=dates)

    # Forward-fill gaps
    df = df.ffill()

    # Attach provenance metadata
    df.attrs["data_source"] = data_source
    df.attrs["is_synthetic"] = is_synthetic

    # Persist to cache ONLY if genuine live market data was downloaded
    if data_source == "yfinance" and not is_synthetic:
        try:
            cache_label = "_".join(sorted(tickers))
            cache_file = _cache_path(cache_label, start, end)
            df.to_csv(cache_file)
            logger.info("Cached prices → %s", cache_file)
        except OSError:
            logger.warning("Could not write cache file for %s", tickers)
    else:
        logger.warning(
            "Synthetic prices generated for %s. Skipping persistent cache write to prevent polluting %s.",
            tickers, _CACHE_DIR,
        )

    return df


def get_sector_constituents(sector: str) -> list[str]:
    """Return NSE tickers belonging to a NIFTY sectoral index.

    Args:
        sector: One of ``"NIFTY_IT"``, ``"NIFTY_BANK"``, ``"NIFTY_AUTO"``,
            ``"NIFTY_PHARMA"``, ``"NIFTY_PSU_BANK"`` (case-insensitive,
            spaces/hyphens are normalised to underscores).

    Returns:
        A list of Yahoo Finance ticker strings (with ``.NS`` suffix).

    Raises:
        KeyError: If *sector* is not recognised.
    """
    key = sector.upper().replace(" ", "_").replace("-", "_")
    if key not in _SECTOR_CONSTITUENTS:
        available = ", ".join(sorted(_SECTOR_CONSTITUENTS))
        raise KeyError(
            f"Unknown sector '{sector}'. Available: {available}"
        )
    return list(_SECTOR_CONSTITUENTS[key])


# ---------------------------------------------------------------------------
# Real Fundamentals Loader (from CSV)
# ---------------------------------------------------------------------------


def get_fundamentals(
    ticker: str,
    csv_path: Path | str | None = None,
) -> dict[str, Any]:
    """Fetch fundamental metrics for *ticker* from real fundamentals CSV.

    Loads data from ``data/fundamentals.csv`` (or ``data/fundamentals_2026-10-30.csv``).
    Treats missing, blank, whitespace, or NaN cells strictly as ``None``
    (never replaces missing fundamentals with 0 or synthetic numbers).

    Args:
        ticker: Symbol string (e.g. ``"TCS.NS"``).
        csv_path: Optional custom CSV path.

    Returns:
        Dict with keys ``ticker``, ``company_name``, ``market_cap``,
        ``pe_ratio``, ``trailing_pe``, ``forward_pe``, ``roe``,
        ``revenue_growth``, ``debt_to_equity``, ``profit_margins``,
        ``data_source`` ('fundamentals_csv'), and ``is_synthetic`` (False).

    Raises:
        KeyError: If ticker is not found in the fundamentals dataset.
        FileNotFoundError: If the fundamentals CSV cannot be found.
    """
    target_path = Path(csv_path) if csv_path is not None else None
    if target_path is None:
        if _DEFAULT_FUNDAMENTALS_CSV.exists():
            target_path = _DEFAULT_FUNDAMENTALS_CSV
        elif _FALLBACK_FUNDAMENTALS_CSV.exists():
            target_path = _FALLBACK_FUNDAMENTALS_CSV
        else:
            raise FileNotFoundError(
                f"Fundamentals CSV not found at {_DEFAULT_FUNDAMENTALS_CSV} or {_FALLBACK_FUNDAMENTALS_CSV}"
            )
    elif not target_path.exists():
        raise FileNotFoundError(f"Fundamentals CSV not found at {target_path}")

    df = pd.read_csv(target_path)
    if "ticker" not in df.columns:
        raise ValueError(f"Malformed fundamentals CSV: missing 'ticker' column in {target_path}")

    matched = df[df["ticker"].astype(str).str.strip() == ticker.strip()]
    if matched.empty:
        logger.warning("Ticker %s not found in fundamentals CSV: %s", ticker, target_path)
        raise KeyError(f"Ticker '{ticker}' not found in fundamentals CSV: {target_path}")

    row = matched.iloc[0]

    def _clean_val(val: Any) -> float | None:
        if pd.isna(val):
            return None
        if isinstance(val, str) and not val.strip():
            return None
        try:
            f = float(val)
            return None if np.isnan(f) else f
        except (ValueError, TypeError):
            return None

    trailing_pe = _clean_val(row.get("trailing_pe"))
    forward_pe = _clean_val(row.get("forward_pe"))
    pe_ratio = trailing_pe if (trailing_pe is not None and trailing_pe > 0) else (
        forward_pe if (forward_pe is not None and forward_pe > 0) else None
    )
    roe = _clean_val(row.get("return_on_equity"))
    revenue_growth = _clean_val(row.get("revenue_growth"))
    debt_to_equity = _clean_val(row.get("debt_to_equity"))
    profit_margins = _clean_val(row.get("profit_margins"))
    market_cap = _clean_val(row.get("market_cap"))

    company_name = str(row.get("company_name", "")).strip() or None
    sector = str(row.get("sector", "")).strip() or None
    industry = str(row.get("industry", "")).strip() or None

    return {
        "ticker": ticker,
        "company_name": company_name,
        "market_cap": market_cap,
        "pe_ratio": pe_ratio,
        "trailing_pe": trailing_pe,
        "forward_pe": forward_pe,
        "roe": roe,
        "revenue_growth": revenue_growth,
        "debt_to_equity": debt_to_equity,
        "profit_margins": profit_margins,
        "sector": sector,
        "industry": industry,
        "data_source": "fundamentals_csv",
        "is_synthetic": False,
    }


# ---------------------------------------------------------------------------
# Real NSE F&O Lot Sizes Loader (from CSV)
# ---------------------------------------------------------------------------


def get_fno_lot_sizes(csv_path: Path | str | None = None) -> dict[str, int]:
    """Load official NSE F&O lot sizes from CSV.

    Args:
        csv_path: Optional custom path to nse_lot_sizes.csv.
            Defaults to ``data/nse_lot_sizes.csv``.

    Returns:
        Dict mapping ticker string to positive integer lot size.

    Raises:
        FileNotFoundError: If the CSV file does not exist.
        ValueError: If no valid lot sizes could be loaded from the CSV.
    """
    path = Path(csv_path) if csv_path is not None else _DEFAULT_LOT_SIZES_CSV
    if not path.exists():
        raise FileNotFoundError(f"NSE lot sizes CSV not found at {path}")

    df = pd.read_csv(path)
    if "ticker" not in df.columns or "lot_size" not in df.columns:
        raise ValueError(f"CSV at {path} missing required 'ticker' or 'lot_size' columns.")

    lot_sizes: dict[str, int] = {}
    for _, row in df.iterrows():
        ticker_val = row.get("ticker")
        if pd.isna(ticker_val):
            continue
        ticker = str(ticker_val).strip()
        if not ticker:
            continue

        raw_size = row.get("lot_size")
        try:
            if pd.isna(raw_size):
                continue
            size = int(float(raw_size))
            if size <= 0:
                logger.warning("Invalid non-positive lot size %s for %s, skipping.", size, ticker)
                continue
            if ticker in lot_sizes:
                logger.warning("Duplicate lot size for %s encountered in %s, retaining first.", ticker, path)
                continue
            lot_sizes[ticker] = size
        except (ValueError, TypeError) as exc:
            logger.warning("Malformed lot size '%s' for %s: %s, skipping.", raw_size, ticker, exc)
            continue

    if not lot_sizes:
        raise ValueError(f"No valid lot sizes found in {path}")

    return lot_sizes
