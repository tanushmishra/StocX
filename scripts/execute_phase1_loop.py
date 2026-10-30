"""
Phase 1 Master Autonomous Execution Script for StocX Data Engineering.
Executes all 24 sector/regime combinations sequentially with:
- Zero overwrite of existing verified datasets.
- Shared in-memory caching per regime to respect API rate limits.
- Deep verification per dataset (structure, date monotonicity, nulls, zeroes, min/max).
- Error isolation and logging.
- Aggregation of full metrics for Phase 1 audit and data dictionary.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import numpy as np

import config
from scripts.download_historical_data import (
    download_sector_regime,
    compute_max_drawdown,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("Phase1Loop")

DATA_DIR = Path("data")

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


def audit_single_dataset(file_path: Path, sector: str, regime_key: str) -> dict[str, Any]:
    """Perform rigorous validation of an existing or newly generated historical dataset."""
    if not file_path.exists():
        return {
            "status": "BLOCKED",
            "file": str(file_path),
            "error": "File does not exist on disk.",
        }

    df = pd.read_csv(file_path)
    configured_tickers = list(config.SECTOR_TICKERS[sector])
    benchmark = config.DEFAULT_BENCHMARK

    # 1. Structure checks
    first_col = df.columns[0]
    last_col = df.columns[-1]
    is_date_first = (first_col == "Date")
    is_bench_last = (last_col == benchmark)
    no_duplicate_cols = (len(df.columns) == len(set(df.columns)))

    # Dates
    dates = pd.to_datetime(df["Date"], format="%Y-%m-%d", errors="coerce")
    is_date_valid = dates.notna().all()
    is_date_unique = df["Date"].is_unique
    is_date_ascending = df["Date"].is_monotonic_increasing

    # Constituent coverage
    constituent_cols = [c for c in df.columns if c not in ["Date", benchmark]]
    dropped_tickers = [t for t in configured_tickers if t not in constituent_cols]

    # Data Quality: per ticker nulls, zeroes, min, max
    ticker_stats = {}
    total_zeroes = 0
    total_nulls = 0

    for col in df.columns:
        if col == "Date":
            continue
        s = pd.to_numeric(df[col], errors="coerce")
        n_null = int(s.isna().sum())
        n_zero = int((s == 0).sum())
        total_nulls += n_null
        total_zeroes += n_zero
        ticker_stats[col] = {
            "observations": len(s),
            "missing_values": n_null,
            "zero_values": n_zero,
            "min_price": float(round(s.min(), 2)) if s.notna().any() else None,
            "max_price": float(round(s.max(), 2)) if s.notna().any() else None,
        }

    # Benchmark metrics
    bench_series = pd.Series(df[benchmark].values, index=df["Date"])
    drawdown_stats = compute_max_drawdown(bench_series)

    # Verdict
    has_structure_error = not (is_date_first and is_bench_last and is_date_valid and is_date_unique and is_date_ascending)
    has_zero_error = (total_zeroes > 0)

    if has_structure_error or has_zero_error:
        verdict = "FAIL"
    elif len(dropped_tickers) > 0 or total_nulls > 0:
        verdict = "PASS WITH LIMITATIONS"
    else:
        verdict = "PASS"

    return {
        "sector": sector,
        "regime": regime_key,
        "file_relative": str(file_path.as_posix()),
        "file_size_bytes": file_path.stat().st_size,
        "row_count": len(df),
        "column_count": len(df.columns),
        "date_range": (str(df["Date"].iloc[0]), str(df["Date"].iloc[-1])),
        "is_date_first": is_date_first,
        "is_bench_last": is_bench_last,
        "is_date_ascending": is_date_ascending,
        "is_date_unique": is_date_unique,
        "configured_ticker_count": len(configured_tickers),
        "retained_ticker_count": len(constituent_cols),
        "retained_tickers": constituent_cols,
        "dropped_tickers": dropped_tickers,
        "total_nulls": total_nulls,
        "total_zeroes": total_zeroes,
        "ticker_stats": ticker_stats,
        "benchmark_drawdown": drawdown_stats,
        "verdict": verdict,
    }


def run_phase1_loop():
    logger.info("==================================================================")
    logger.info("STARTING PHASE 1 DATA INGESTION & AUDIT LOOP")
    logger.info("Target: 6 sectors x 4 regimes = 24 combinations")
    logger.info("==================================================================")

    all_results = {}
    summary_matrix = {s: {} for s in SECTORS}

    for regime in REGIMES:
        logger.info("\n>>> PROCESSING REGIME: %s (%s to %s)",
                    regime,
                    config.CRASH_REGIMES[regime]["start"],
                    config.CRASH_REGIMES[regime]["end"])
        shared_regime_cache: dict[tuple[str, str, str], pd.Series] = {}

        for sector in SECTORS:
            combo_key = f"{sector}__{regime}"
            filename = f"{sector}__{regime.lower()}.csv"
            out_path = DATA_DIR / filename

            logger.info("--- [%s] Target: %s ---", combo_key, out_path)

            try:
                # download_sector_regime respects overwrite=False and skips existing files
                csv_path, download_rep = download_sector_regime(
                    sector=sector,
                    regime_key=regime,
                    overwrite=False,
                    cache=shared_regime_cache,
                    delay=0.5,
                )
                if download_rep.get("status") == "skipped_existing":
                    logger.info("Skipped existing file (preserved without overwrite): %s", csv_path)
                else:
                    logger.info("Download completed successfully: %s", csv_path)
                    if download_rep.get("failed_tickers"):
                        logger.info("Documented dropped tickers: %s", download_rep["failed_tickers"])

                # Run post-download validation audit
                audit_rep = audit_single_dataset(csv_path, sector, regime)
                # Attach downloader notes if available
                if "failed_tickers" in download_rep:
                    audit_rep["failed_ticker_reasons"] = download_rep["failed_tickers"]

                all_results[combo_key] = audit_rep
                summary_matrix[sector][regime] = audit_rep["verdict"]
                logger.info("Audit Result for %s: %s (Rows: %d, Cols: %d, Nulls: %d, Zeroes: %d)",
                            combo_key, audit_rep["verdict"], audit_rep["row_count"],
                            audit_rep["column_count"], audit_rep["total_nulls"], audit_rep["total_zeroes"])

            except Exception as exc:
                logger.error("FATAL ERROR processing %s: %s", combo_key, exc, exc_info=True)
                err_rep = {
                    "sector": sector,
                    "regime": regime,
                    "verdict": "BLOCKED",
                    "error": str(exc),
                }
                all_results[combo_key] = err_rep
                summary_matrix[sector][regime] = "BLOCKED"

    # Save complete audit dictionary to JSON for documentation generation
    audit_json_path = DATA_DIR / "phase_1_audit_results.json"
    with open(audit_json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2)

    logger.info("\n==================================================================")
    logger.info("PHASE 1 INGESTION COMPLETE. AUDIT SUMMARY MATRIX:")
    logger.info("==================================================================")
    print(f"\n{'Sector':<20} | {'COVID_2020':<12} | {'ELECTION_2024':<14} | {'TECH_SELLOFF_2022':<18} | {'2008_GFC':<12}")
    print("-" * 85)
    for sector in SECTORS:
        row = summary_matrix[sector]
        print(f"{sector:<20} | {row.get('COVID_2020', 'N/A'):<12} | {row.get('ELECTION_2024', 'N/A'):<14} | {row.get('TECH_SELLOFF_2022', 'N/A'):<18} | {row.get('2008_GFC', 'N/A'):<12}")

    return all_results, summary_matrix


if __name__ == "__main__":
    run_phase1_loop()
