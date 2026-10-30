"""
Fundamentals Ingestion Script for StocX
Fetches fundamental metrics for all candidate tickers configured in config.py via yfinance.
Saves to data/fundamentals_2026-10-30.csv per data contract rules:
- Missing values remain blank/NaN, NEVER replaced with 0.
- Handles missing tickers and API errors gracefully.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
import pandas as pd
import yfinance as yf

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
OUT_FILE = DATA_DIR / "fundamentals_2026-10-30.csv"


def collect_fundamentals() -> tuple[Path, pd.DataFrame, dict]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Identify all configured tickers in config.py
    sector_tickers = set()
    for s, t_list in config.SECTOR_TICKERS.items():
        sector_tickers.update(t_list)
    fno_tickers = set(t for t in config.FNO_LOT_SIZES.keys() if t.endswith(".NS"))
    all_tickers = sorted(sector_tickers.union(fno_tickers))

    logger.info("Total configured unique candidate tickers: %d", len(all_tickers))

    records = []
    failed_tickers = {}
    successful_tickers = []

    for idx, ticker in enumerate(all_tickers, 1):
        logger.info("[%d/%d] Fetching fundamentals for %s...", idx, len(all_tickers), ticker)
        try:
            tk = yf.Ticker(ticker)
            info = tk.info or {}

            # Detect if ticker failed (empty info or no basic attributes)
            company_name = info.get("longName") or info.get("shortName")
            market_cap = info.get("marketCap")

            if not company_name and not market_cap:
                # Ticker returned no meaningful fundamental data
                failed_tickers[ticker] = "No company info or quote summary returned by Yahoo Finance (HTTP 404 / inactive symbol)"
                continue

            trailing_pe = info.get("trailingPE")
            forward_pe = info.get("forwardPE")

            roe = info.get("returnOnEquity")
            rev_growth = info.get("revenueGrowth")
            debt_to_equity = info.get("debtToEquity")
            profit_margins = info.get("profitMargins")
            sector = info.get("sector")
            industry = info.get("industry")

            record = {
                "ticker": ticker,
                "company_name": company_name,
                "market_cap": market_cap,
                "trailing_pe": trailing_pe,
                "forward_pe": forward_pe,
                "return_on_equity": roe,
                "revenue_growth": rev_growth,
                "debt_to_equity": debt_to_equity,
                "profit_margins": profit_margins,
                "sector": sector,
                "industry": industry,
            }
            records.append(record)
            successful_tickers.append(ticker)

        except Exception as exc:
            logger.warning("Error fetching %s: %s", ticker, exc)
            failed_tickers[ticker] = f"API error: {str(exc)}"

    # 2. Build DataFrame
    df = pd.DataFrame(records)

    # 3. Save to CSV ensuring empty/NaN values remain blank (na_rep="")
    df.to_csv(OUT_FILE, index=False, na_rep="")
    logger.info("Saved fundamentals to %s with %d rows", OUT_FILE, len(df))

    # 4. Reopen and validate saved CSV
    reloaded_df = pd.read_csv(OUT_FILE)
    
    validation_report = {
        "file_path": str(OUT_FILE.resolve()),
        "file_relative": str(OUT_FILE),
        "total_candidate_tickers": len(all_tickers),
        "successful_count": len(successful_tickers),
        "failed_count": len(failed_tickers),
        "successful_tickers": successful_tickers,
        "failed_tickers": failed_tickers,
        "row_count": len(reloaded_df),
        "column_count": len(reloaded_df.columns),
        "columns": list(reloaded_df.columns),
        "blank_counts": {col: int(reloaded_df[col].isna().sum()) for col in reloaded_df.columns},
        "zero_counts": {
            col: int((reloaded_df[col] == 0).sum())
            for col in reloaded_df.select_dtypes(include=["number"]).columns
        },
    }

    return OUT_FILE, reloaded_df, validation_report


if __name__ == "__main__":
    out_path, df, rep = collect_fundamentals()
    print("\n=== FUNDAMENTALS COLLECTION REPORT ===")
    print("File:", rep["file_relative"])
    print("Candidates:", rep["total_candidate_tickers"])
    print("Successful:", rep["successful_count"])
    print("Failed:", rep["failed_count"])
    print("Failed Tickers:", rep["failed_tickers"])
    print("Blank counts per metric:", rep["blank_counts"])
    print("Zero counts in numeric metrics:", rep["zero_counts"])
    print("\nHead (first 3 rows):")
    print(df.head(3).to_string())
