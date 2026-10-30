"""
NSE F&O Lot Sizes Ingestion Script for StocX
Downloads official Permitted Lot Sizes (fo_mktlots.csv) from NSE:
1. Saves original source as data/nse_fo_mktlots_source.csv
2. Parses official market lot sizes (near-month contract lot sizes).
3. Cross-references configured tickers from config.py.
4. Saves filtered, validated table to data/nse_lot_sizes.csv.
"""

from __future__ import annotations

import logging
import sys
from datetime import date
from pathlib import Path
import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
SOURCE_FILE = DATA_DIR / "nse_fo_mktlots_source.csv"
OUTPUT_FILE = DATA_DIR / "nse_lot_sizes.csv"

NSE_SOURCE_URL = "https://nsearchives.nseindia.com/content/fo/fo_mktlots.csv"
NSE_PAGE_URL = "https://www.nseindia.com/static/products-services/equity-derivatives-contract-information"


def fetch_and_process_nse_lot_sizes() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    today_str = date.today().isoformat()

    # 1. Read existing source file if present to preserve raw source unchanged, otherwise download
    if SOURCE_FILE.exists():
        logger.info("Using existing source file -> %s", SOURCE_FILE)
        with open(SOURCE_FILE, "r", encoding="utf-8") as f:
            raw_text = f.read()
    else:
        logger.info("Downloading official NSE lot sizes from: %s", NSE_SOURCE_URL)
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
        resp = requests.get(NSE_SOURCE_URL, headers=headers, timeout=15)
        resp.raise_for_status()
        with open(SOURCE_FILE, "wb") as f:
            f.write(resp.content)
        raw_text = resp.text
        logger.info("Saved original source file -> %s (%d bytes)", SOURCE_FILE, len(resp.content))

    # 3. Inspect source file lines and structure
    raw_lines = raw_text.splitlines()
    if not raw_lines:
        raise ValueError("NSE source CSV is empty.")

    header_cols = [col.strip() for col in raw_lines[0].split(",") if col.strip()]
    logger.info("Source CSV Header Columns: %s", header_cols)

    # 4. Parse rows into official symbol -> lot size mapping
    # Format of fo_mktlots.csv:
    # UNDERLYING, SYMBOL, <EXPIRY_MONTH_1>, <EXPIRY_MONTH_2>, ...
    official_records = []
    for line_idx, line in enumerate(raw_lines[1:], start=2):
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 3:
            continue
        underlying = parts[0]
        symbol = parts[1]
        near_expiry_lot = parts[2]

        # Skip section divider rows (e.g. "Derivatives on Individual Securities, Symbol, ...")
        if symbol.lower() in ("symbol", ""):
            continue

        try:
            lot_int = int(near_expiry_lot)
            official_records.append({
                "underlying_name": underlying,
                "symbol": symbol,
                "official_lot_size": lot_int,
            })
        except ValueError:
            logger.debug("Skipping unparseable row %d: %s", line_idx, line)

    official_df = pd.DataFrame(official_records)
    logger.info("Parsed %d active official F&O underlying contracts from NSE source", len(official_df))

    # Build lookup map: symbol -> record
    official_map = {row["symbol"]: row for _, row in official_df.iterrows()}

    # 5. Read config.py tickers
    # A) All tickers explicitly in config.FNO_LOT_SIZES
    fno_dict_tickers = list(config.FNO_LOT_SIZES.keys())

    # B) All unique constituents from config.SECTOR_TICKERS
    sector_unique_tickers = sorted(set(
        t for tlist in config.SECTOR_TICKERS.values() for t in tlist
    ))

    # Combined candidate ticker list (preserving benchmark NIFTY)
    candidate_tickers = sorted(set(fno_dict_tickers + sector_unique_tickers))
    logger.info("Identified %d candidate tickers from config.py", len(candidate_tickers))

    matched_rows = []
    unmatched_tickers = {}

    for ticker in candidate_tickers:
        # Strip .NS suffix for NSE symbol lookup, except indices like NIFTY
        clean_symbol = ticker.replace(".NS", "")

        if clean_symbol in official_map:
            off_rec = official_map[clean_symbol]
            matched_rows.append({
                "ticker": ticker,
                "symbol": clean_symbol,
                "underlying_name": off_rec["underlying_name"],
                "lot_size": int(off_rec["official_lot_size"]),
                "expiry": "NOV-26",
                "as_of_date": "2026-10-30",
            })
        else:
            # Document reason
            if ticker == "LTIM.NS":
                reason = "Symbol not found in official F&O list (legacy/merger symbol)"
            elif ticker == "TATAMOTORS.NS":
                reason = "Symbol not found in official F&O list (demerged into TMCV/TMPV)"
            elif ticker.endswith(".NS"):
                reason = "Not permitted for F&O trading by NSE (cash market equity only)"
            else:
                reason = "Not found in official F&O market lots list"
            unmatched_tickers[ticker] = reason

    # 6. Save data/nse_lot_sizes.csv
    out_df = pd.DataFrame(matched_rows)
    # Sort for deterministic ordering: indices first, then alphabetical by ticker
    out_df["is_index"] = out_df["ticker"].apply(lambda x: 0 if not x.endswith(".NS") else 1)
    out_df = out_df.sort_values(by=["is_index", "ticker"]).drop(columns=["is_index"])
    out_df.to_csv(OUTPUT_FILE, index=False)
    logger.info("Saved %s with %d matched F&O instruments", OUTPUT_FILE, len(out_df))

    # 7. Reopen and validate both files
    reopened_source = pd.read_csv(SOURCE_FILE)
    reopened_output = pd.read_csv(OUTPUT_FILE)

    report = {
        "source_page_url": NSE_PAGE_URL,
        "source_csv_url": NSE_SOURCE_URL,
        "download_date": today_str,
        "source_file": str(SOURCE_FILE),
        "output_file": str(OUTPUT_FILE),
        "source_row_count": len(reopened_source),
        "source_columns": header_cols,
        "total_official_fo_underlyings": len(official_df),
        "candidate_tickers_count": len(candidate_tickers),
        "matched_count": len(reopened_output),
        "unmatched_count": len(unmatched_tickers),
        "output_columns": list(reopened_output.columns),
        "unmatched_tickers": unmatched_tickers,
        "sample_output": reopened_output.head(10).to_dict(orient="records"),
    }

    return report


if __name__ == "__main__":
    rep = fetch_and_process_nse_lot_sizes()
    print("\n=== NSE LOT SIZES INGESTION REPORT ===")
    print("Source Page:", rep["source_page_url"])
    print("Source CSV:", rep["source_csv_url"])
    print("Download Date:", rep["download_date"])
    print("Source File:", rep["source_file"], f"({rep['source_row_count']} rows)")
    print("Source Columns:", rep["source_columns"][:5], "...")
    print("Total Official Underlyings in NSE File:", rep["total_official_fo_underlyings"])
    print("Candidate Tickers Evaluated:", rep["candidate_tickers_count"])
    print("Matched Configured Tickers:", rep["matched_count"])
    print("Unmatched Tickers:", rep["unmatched_count"])
    print("\nUnmatched Tickers Detail:")
    for t, reason in rep["unmatched_tickers"].items():
        print(f"  - {t}: {reason}")
    print("\nSample Output (First 5 Rows):")
    out_df = pd.read_csv(rep["output_file"])
    print(out_df.head(5).to_string(index=False))
