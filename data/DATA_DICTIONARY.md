# StocX — Data Dictionary

**Version:** 1.0.0  
**Author:** Data Engineering (`anaytiwari/data`)  
**As of Date:** 2026-10-30  

---

## 1. Overview & Repository Data Layout

The `data/` directory contains all foundational quantitative and market inputs for StocX:
```text
data/
├── NIFTY_<SECTOR>__<regime>.csv      # 24 historical crisis price datasets
├── fundamentals_2026-10-30.csv       # Point-in-time fundamentals for pair screening
├── nse_lot_sizes.csv                 # Permitted F&O contract lot sizes for execution
├── nse_fo_mktlots_source.csv         # Raw official lot size circular from NSE India
├── PHASE_1_DATA_AUDIT.md             # Complete data engineering verification audit
└── DATA_DICTIONARY.md                # This specification document
```

## 2. Historical Price Datasets (`data/<SECTOR>__<regime>.csv`)

### Purpose

Provides split- and dividend-adjusted daily closing prices for sector equities and the market benchmark across 4 historical stress regimes. Used by `engine/beta_calculator.py`, `engine/cointegration.py`, and `engine/portfolio.py` to calculate covariance, cointegration, hedge ratios, and backtested drawdowns.

### File Naming Convention

`data/<SECTOR>__<regime_lower>.csv`  
Examples: `data/NIFTY_IT__covid_2020.csv`, `data/NIFTY_BANK__election_2024.csv`

### Schema & Column Specifications

| Column Name | Type | Unit / Format | Description |
| :--- | :--- | :--- | :--- |
| `Date` | String | `YYYY-MM-DD` | Official NSE trading session date. Strictly ascending and unique. |
| `<TICKER>.NS` | Float | INR (₹) | Adjusted daily closing price of the sector constituent stock. |
| `^NSEI` | Float | Index Points | NIFTY 50 Benchmark daily adjusted close. Strictly the final column. |

### Data Conventions & Invariants

- **Missing Value Representation:** Empty string `,,` in CSV; loaded as `NaN` in pandas. Never zero.
- **Zero Policy:** Strict prohibition of `0.0` or synthetic prices. Total zeros across all datasets = 0.
- **Calendar Alignment:** Tickers are aligned to the official trading sessions of the benchmark `^NSEI`.
- **Adjusted Prices:** Accounts for stock splits, bonus issues, and cash dividends to prevent artificial price jumps.

### Configured Sectors & Stress Regimes

- **Sectors (6):** `NIFTY_IT`, `NIFTY_BANK`, `NIFTY_AUTO`, `NIFTY_PHARMA`, `NIFTY_PSU_BANK`, `NIFTY_PRIVATE_BANK`.
- **Regimes (4):**
  - `COVID_2020`: `2020-01-01` to `2020-06-30` (122 trading sessions, -38.44% benchmark drawdown).
  - `ELECTION_2024`: `2024-05-15` to `2024-06-15` (22 trading sessions, -5.93% benchmark drawdown).
  - `TECH_SELLOFF_2022`: `2022-01-01` to `2022-12-31` (248 trading sessions, -16.47% benchmark drawdown).
  - `2008_GFC`: `2008-01-01` to `2009-03-31` (303 trading sessions, -59.86% benchmark drawdown).

## 3. Company Fundamentals (`data/fundamentals_2026-10-30.csv`)

### Purpose

Supplies quantitative valuation and quality metrics for fundamental pair ranking (`Fundamental Screener Agent`). Identifies fundamentally strong candidates (high ROE, reasonable P/E) for Long legs and weak candidates for Short legs.

### Schema & Column Specifications

| Column Name | Type | Unit | Description | Null Policy |
| :--- | :--- | :--- | :--- | :--- |
| `ticker` | String | Symbol | Yahoo Finance NSE symbol (e.g. `TCS.NS`). Unique key. | Required |
| `company_name` | String | Text | Official legal or operating name of the company. | Required |
| `market_cap` | Float | INR (₹) | Full equity market capitalization. | Required (>0) |
| `trailing_pe` | Float | Ratio | Trailing Twelve Months Price-to-Earnings ratio. | Blank if loss-making |
| `forward_pe` | Float | Ratio | 1-Year Forward consensus Price-to-Earnings ratio. | Blank if unavailable |
| `return_on_equity` | Float | Decimal | TTM Net Income / Shareholders' Equity (e.g. 0.35 = 35%). | Blank if unavailable |
| `revenue_growth` | Float | Decimal | Year-over-year quarterly revenue growth rate. | Blank if unavailable |
| `debt_to_equity` | Float | Percentage | Total Debt / Total Equity (e.g. 15.5 = 15.5%). Blank for banks. | Blank for financials |
| `profit_margins` | Float | Decimal | TTM Net Profit Margin (e.g. 0.20 = 20%). | Blank if unavailable |
| `sector` | String | Category | StocX sector classification (e.g. `NIFTY_IT`). | Required |
| `industry` | String | Text | Detailed industrial sub-sector from exchange classification. | Required |

### Important Usage Notes

- **Snapshot Date:** Current fundamentals as of `2026-10-30`. Not historical 2020/2008 balance sheets.
- **Debt-to-Equity on Banks:** Omitted (blank) for banking and financial entities because traditional debt-to-equity is non-standard for deposit-taking institutions.
- **P/E Fields:** `trailing_pe` and `forward_pe` are kept distinct to prevent conflating historical earnings with analyst forward projections.

## 4. Official NSE F&O Lot Sizes (`data/nse_lot_sizes.csv`)

### Purpose

Provides the official permitted market lot sizes for NSE equity derivative contracts. Used by `engine/portfolio.py` (`calculate_lot_sizes()`) to round theoretical beta-neutral cash weights into executable whole derivative contracts.

### Schema & Column Specifications

| Column Name | Type | Format / Example | Description |
| :--- | :--- | :--- | :--- |
| `ticker` | String | `RELIANCE.NS` | StocX symbol matching `config.py`. |
| `symbol` | String | `RELIANCE` | Official NSE exchange derivative symbol. |
| `underlying_name` | String | `RELIANCE INDUSTRIES LTD` | Full underlying company name from NSE. |
| `lot_size` | Integer | `250` | Number of underlying shares per 1 derivative contract. |
| `expiry` | String | `NOV-26` | Active contract expiry cycle corresponding to the lot size. |
| `as_of_date` | String | `2026-10-30` | Date of ingestion from the NSE circular. |

### Data Provenance & Integrity

- **Official Source:** Downloaded from NSE India Equity Derivatives circular (`fo_mktlots.csv`).
- **Raw Source Preserved:** `data/nse_fo_mktlots_source.csv`.
- **Missing Contract Handling:** If a cash constituent is not traded in F&O (e.g. `LTTS`), downstream execution safely bypasses contract lot conversion and reports cash-market sizing.
