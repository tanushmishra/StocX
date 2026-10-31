"""
Global configuration for the Market-Neutral Hedge Builder.

Loads settings from environment variables (.env file) with sensible defaults.
All configuration is centralized here to avoid magic numbers scattered across modules.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file if present
load_dotenv()


# ──────────────────────────────────────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
DATA_CACHE_DIR = PROJECT_ROOT / os.getenv("DATA_CACHE_DIR", "data_cache")
DATA_CACHE_DIR.mkdir(exist_ok=True)

# ──────────────────────────────────────────────────────────────────────────────
# Market Defaults
# ──────────────────────────────────────────────────────────────────────────────
DEFAULT_BENCHMARK: str = os.getenv("DEFAULT_BENCHMARK", "^NSEI")
RISK_FREE_RATE: float = float(os.getenv("RISK_FREE_RATE", "0.068"))
DEFAULT_CAPITAL: float = float(os.getenv("DEFAULT_CAPITAL", "100000"))
TRADING_DAYS_PER_YEAR: int = 252

# ──────────────────────────────────────────────────────────────────────────────
# Agent & LLM Configuration
# ──────────────────────────────────────────────────────────────────────────────
GOOGLE_API_KEY: str | None = os.getenv("GOOGLE_API_KEY")
TAVILY_API_KEY: str | None = os.getenv("TAVILY_API_KEY")

MAX_PAIR_ATTEMPTS: int = int(os.getenv("MAX_PAIR_ATTEMPTS", "5"))
GEMINI_FAST_MODEL: str = os.getenv("GEMINI_FAST_MODEL", "gemini-3.8-flash")
FAST_LLM_MODEL: str = os.getenv("FAST_LLM_MODEL", GEMINI_FAST_MODEL)
GEMINI_PRO_MODEL: str = os.getenv("GEMINI_PRO_MODEL", "gemini-3.1-pro-preview")
REASONING_LLM_MODEL: str = os.getenv("REASONING_LLM_MODEL", GEMINI_PRO_MODEL)
LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "3"))
LLM_RETRY_BACKOFF: float = float(os.getenv("LLM_RETRY_BACKOFF", "2.0"))
ALLOW_SYNTHETIC: bool = os.getenv("ALLOW_SYNTHETIC", "false").lower() in ("true", "1", "yes")

# Fundamentals data path
FUNDAMENTALS_CSV_PATH: Path = PROJECT_ROOT / os.getenv("FUNDAMENTALS_CSV_PATH", "data/fundamentals.csv")

# ──────────────────────────────────────────────────────────────────────────────
# Verification Guardrail Thresholds
# ──────────────────────────────────────────────────────────────────────────────
MIN_CORRELATION: float = 0.65
MAX_COINT_PVALUE: float = 0.05
MAX_HEDGED_BETA: float = 0.15
MAX_DRAWDOWN_REDUCTION_RATIO: float = 0.50  # Hedged MDD must be < 50% of unhedged

# ──────────────────────────────────────────────────────────────────────────────
# Crash Regime Definitions (for stress testing)
# ──────────────────────────────────────────────────────────────────────────────
CRASH_REGIMES: dict[str, dict[str, str]] = {
    "2008_GFC": {
        "name": "2008 Global Financial Crisis",
        "start": "2008-01-01",
        "end": "2009-03-31",
        "description": "Lehman Brothers collapse, global credit freeze",
    },
    "COVID_2020": {
        "name": "March 2020 COVID Lockdown",
        "start": "2020-01-01",
        "end": "2020-06-30",
        "description": "Pandemic-driven market crash and recovery",
    },
    "TECH_SELLOFF_2022": {
        "name": "2022 Global Tech Selloff",
        "start": "2022-01-01",
        "end": "2022-12-31",
        "description": "Rising interest rates crushing tech valuations",
    },
    "ELECTION_2024": {
        "name": "June 4, 2024 Election Results Day",
        "start": "2024-05-15",
        "end": "2024-06-15",
        "description": "Indian general election results shock",
    },
}

# ──────────────────────────────────────────────────────────────────────────────
# Sector Constituent Tickers (NSE)
# ──────────────────────────────────────────────────────────────────────────────
SECTOR_TICKERS: dict[str, list[str]] = {
    "NIFTY_IT": [
        "TCS.NS", "INFY.NS", "HCLTECH.NS", "WIPRO.NS",
        "TECHM.NS", "LTIM.NS", "MPHASIS.NS", "COFORGE.NS",
        "PERSISTENT.NS", "LTTS.NS",
    ],
    "NIFTY_BANK": [
        "HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS", "AXISBANK.NS",
        "SBIN.NS", "BANKBARODA.NS", "PNB.NS", "INDUSINDBK.NS",
        "BANDHANBNK.NS", "FEDERALBNK.NS", "IDFCFIRSTB.NS", "AUBANK.NS",
    ],
    "NIFTY_PSU_BANK": [
        "SBIN.NS", "BANKBARODA.NS", "PNB.NS", "CANBK.NS",
        "UNIONBANK.NS", "INDIANB.NS", "BANKINDIA.NS", "MAHABANK.NS",
        "CENTRALBK.NS", "UCOBANK.NS", "IOB.NS", "PSB.NS",
    ],
    "NIFTY_PHARMA": [
        "SUNPHARMA.NS", "DRREDDY.NS", "CIPLA.NS", "DIVISLAB.NS",
        "APOLLOHOSP.NS", "AUROPHARMA.NS", "BIOCON.NS", "LUPIN.NS",
        "TORNTPHARM.NS", "ALKEM.NS",
    ],
    "NIFTY_AUTO": [
        "MARUTI.NS", "M&M.NS", "TATAMOTORS.NS", "BAJAJ-AUTO.NS",
        "HEROMOTOCO.NS", "EICHERMOT.NS", "ASHOKLEY.NS", "TVSMOTOR.NS",
        "BALKRISIND.NS", "BHARATFORG.NS",
    ],
    "NIFTY_PRIVATE_BANK": [
        "HDFCBANK.NS", "ICICIBANK.NS", "KOTAKBANK.NS", "AXISBANK.NS",
        "INDUSINDBK.NS", "FEDERALBNK.NS", "IDFCFIRSTB.NS", "BANDHANBNK.NS",
        "RBLBANK.NS", "AUBANK.NS",
    ],
}

# ──────────────────────────────────────────────────────────────────────────────
# F&O Lot Sizes (approximate, as of 2024; updated periodically by NSE)
# ──────────────────────────────────────────────────────────────────────────────
FNO_LOT_SIZES: dict[str, int] = {
    "TCS.NS": 175,
    "INFY.NS": 400,
    "HCLTECH.NS": 350,
    "WIPRO.NS": 1500,
    "TECHM.NS": 600,
    "LTIM.NS": 150,
    "HDFCBANK.NS": 550,
    "ICICIBANK.NS": 700,
    "KOTAKBANK.NS": 400,
    "AXISBANK.NS": 900,
    "SBIN.NS": 750,
    "BANKBARODA.NS": 2925,
    "PNB.NS": 8000,
    "INDUSINDBK.NS": 500,
    "SUNPHARMA.NS": 700,
    "DRREDDY.NS": 125,
    "CIPLA.NS": 650,
    "MARUTI.NS": 100,
    "TATAMOTORS.NS": 1125,
    "BAJAJ-AUTO.NS": 125,
    "M&M.NS": 350,
    "RELIANCE.NS": 250,
    "NIFTY": 50,  # NIFTY 50 index
}

# ──────────────────────────────────────────────────────────────────────────────
# Transaction Costs (Indian market specifics)
# ──────────────────────────────────────────────────────────────────────────────
BROKERAGE_PCT: float = 0.001  # 0.1% round-trip brokerage
STT_FUTURES_PCT: float = 0.0001  # 0.01% STT on futures sell side
GST_ON_BROKERAGE_PCT: float = 0.18  # 18% GST on brokerage
STAMP_DUTY_PCT: float = 0.00002  # 0.002% stamp duty

TOTAL_TRANSACTION_COST_PCT: float = (
    BROKERAGE_PCT + STT_FUTURES_PCT + BROKERAGE_PCT * GST_ON_BROKERAGE_PCT + STAMP_DUTY_PCT
)
