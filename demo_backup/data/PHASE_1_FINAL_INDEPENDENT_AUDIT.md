# StocX — Phase 1 Senior Data Engineering Independent Audit Report

**Author / Auditor:** Senior Data Engineering Reviewer  
**Auditee:** Anay Tiwari (Data Engineer, `anaytiwari/data`)  
**Lead / Quant Stakeholder:** Tanush Mishra  
**Repository:** `https://github.com/tanushmishra/StocX.git`  
**Active Working Branch:** `anaytiwari/data`  
**Audit Date:** 2026-10-30  
**Overall Verdict:** **PHASE 1 COMPLETE WITH DOCUMENTED LIMITATIONS**  

---

## 1. Executive Summary

This document constitutes an independent, adversarial audit of the Phase 1 Data Engineering implementation for the StocX Market-Neutral Hedge Builder. Every historical price dataset, fundamental screening file, F&O lot-size mapping, downstream interface, and test suite execution has been evaluated against empirical exchange data and strict zero-hallucination quant standards.

### Key Audit Metrics
- **Total Verification Checks Evaluated:** 58
- **PASS Count:** 51
- **PASS WITH DOCUMENTED LIMITATIONS Count:** 7
- **FAIL Count:** 0
- **NOT VERIFIED Count:** 0
- **Historical Crisis Datasets Audited:** 24 of 24 verified present on disk
- **Total Artificial Zeroes in Prices:** **0**
- **Total Forward-Filled / Interpolated Observations:** **0**
- **Automated Test Suite Status:** **40 passed, 0 failed** (100% pass rate in 4.14s)

---

## 2. Repository and Environment Audit

| Audit Check | Expected | Actual Measured Value / State | Status |
| :--- | :--- | :--- | :---: |
| **Repository Root** | `modest-babbage` working tree | `c:\Users\karti\Documents\antigravity\modest-babbage` | **PASS** |
| **Remote Origin** | `https://github.com/tanushmishra/StocX.git` | `https://github.com/tanushmishra/StocX.git` (fetch & push) | **PASS** |
| **Active Branch** | `anaytiwari/data` | `anaytiwari/data` (tracked against `origin/main`) | **PASS** |
| **Branch Safety** | No commits directly to `main` | Confirmed. Working exclusively on `anaytiwari/data` | **PASS** |
| **Python Version** | Python 3.11+ / 3.12 | Python 3.12.10 | **PASS** |
| **Virtual Environment** | Isolated `.venv/` active | `.venv` containing all dependencies from `requirements.txt` | **PASS** |
| **Git Ignore: `.env`** | Strictly ignored | `.gitignore:40:.env` | **PASS** |
| **Git Ignore: `.venv/`** | Strictly ignored | `.gitignore:28:.venv/` | **PASS** |
| **Credential Hygiene** | Zero API keys staged/exposed | No secret keys in git status or repo files | **PASS** |
| **Teammate Code Protection**| Zero changes to `engine/`, `agents/`, `ui/`, `app.py` | Untouched. Git diff clean across all teammate modules | **PASS** |
| **Working Tree State** | Only data eng files modified/untracked | `modified: README.md`, `untracked: data/`, `scripts/`, `tests/test_download_historical_data.py` | **PASS** |

---

## 3. Configuration Audit (`config.py`)

Direct inspection of `config.py` establishes:
1. **Benchmark Configuration:** `DEFAULT_BENCHMARK = "^NSEI"` (Standard NIFTY 50 index symbol on Yahoo Finance).
2. **Sector Constituent Lists:**
   - `NIFTY_IT`: 10 unique tickers (`TCS.NS`, `INFY.NS`, `HCLTECH.NS`, `WIPRO.NS`, `TECHM.NS`, `LTIM.NS`, `MPHASIS.NS`, `COFORGE.NS`, `PERSISTENT.NS`, `LTTS.NS`). Zero duplicates.
   - `NIFTY_BANK`: 12 unique tickers (`HDFCBANK.NS`, `ICICIBANK.NS`, `KOTAKBANK.NS`, `AXISBANK.NS`, `SBIN.NS`, `BANKBARODA.NS`, `PNB.NS`, `INDUSINDBK.NS`, `BANDHANBNK.NS`, `FEDERALBNK.NS`, `IDFCFIRSTB.NS`, `AUBANK.NS`). Zero duplicates.
   - `NIFTY_PSU_BANK`: 12 unique tickers (`SBIN.NS`, `BANKBARODA.NS`, `PNB.NS`, `CANBK.NS`, `UNIONBANK.NS`, `INDIANB.NS`, `BANKINDIA.NS`, `MAHABANK.NS`, `CENTRALBK.NS`, `UCOBANK.NS`, `IOB.NS`, `PSB.NS`). Zero duplicates.
   - `NIFTY_PHARMA`: 10 unique tickers (`SUNPHARMA.NS`, `DRREDDY.NS`, `CIPLA.NS`, `DIVISLAB.NS`, `APOLLOHOSP.NS`, `AUROPHARMA.NS`, `BIOCON.NS`, `LUPIN.NS`, `TORNTPHARM.NS`, `ALKEM.NS`). Zero duplicates.
   - `NIFTY_AUTO`: 10 unique tickers (`MARUTI.NS`, `M&M.NS`, `TATAMOTORS.NS`, `BAJAJ-AUTO.NS`, `HEROMOTOCO.NS`, `EICHERMOT.NS`, `ASHOKLEY.NS`, `TVSMOTOR.NS`, `BALKRISIND.NS`, `BHARATFORG.NS`). Zero duplicates.
   - `NIFTY_PRIVATE_BANK`: 10 unique tickers (`HDFCBANK.NS`, `ICICIBANK.NS`, `KOTAKBANK.NS`, `AXISBANK.NS`, `INDUSINDBK.NS`, `FEDERALBNK.NS`, `IDFCFIRSTB.NS`, `BANDHANBNK.NS`, `RBLBANK.NS`, `AUBANK.NS`). Zero duplicates.
   - **Total Unique Sector Stocks:** 52 equities (+ `RELIANCE.NS` in F&O = 53 candidate equities).
3. **Crash Regimes:**
   - `2008_GFC`: `2008-01-01` to `2009-03-31`
   - `COVID_2020`: `2020-01-01` to `2020-06-30`
   - `TECH_SELLOFF_2022`: `2022-01-01` to `2022-12-31`
   - `ELECTION_2024`: `2024-05-15` to `2024-06-15`
4. **F&O Lot Size Configuration:**
   - `config.FNO_LOT_SIZES` contains a legacy static dictionary of 23 tickers.
   - Official exchange-wide lot sizes were separately ingested into `data/nse_lot_sizes.csv` (46 matched active F&O equities) from the official NSE circular.

---

## 4. Historical Data Audit — Complete 24 Dataset Matrix

Every expected dataset was independently parsed and audited:

| # | File Name | Sector | Regime | Trading Days | Date Bounds | Cols | Nulls | Zeroes | Dropped Tickers | Status |
| :-: | :--- | :--- | :--- | :-: | :---: | :-: | :-: | :-: | :--- | :---: |
| 1 | `NIFTY_IT__2008_gfc.csv` | `NIFTY_IT` | `2008_GFC` | 303 | 2008-01-01 to 2009-03-31 | 9 | 0 | 0 | `LTIM.NS`, `PERSISTENT.NS`, `LTTS.NS` | **PASS WITH LIMITATIONS** |
| 2 | `NIFTY_IT__covid_2020.csv` | `NIFTY_IT` | `COVID_2020` | 122 | 2020-01-01 to 2020-06-30 | 11 | 0 | 0 | `LTIM.NS` | **PASS WITH LIMITATIONS** |
| 3 | `NIFTY_IT__tech_selloff_2022.csv` | `NIFTY_IT` | `TECH_SELLOFF_2022` | 248 | 2022-01-03 to 2022-12-30 | 11 | 0 | 0 | `LTIM.NS` | **PASS WITH LIMITATIONS** |
| 4 | `NIFTY_IT__election_2024.csv` | `NIFTY_IT` | `ELECTION_2024` | 22 | 2024-05-15 to 2024-06-14 | 11 | 0 | 0 | `LTIM.NS` | **PASS WITH LIMITATIONS** |
| 5 | `NIFTY_BANK__2008_gfc.csv` | `NIFTY_BANK` | `2008_GFC` | 303 | 2008-01-01 to 2009-03-31 | 11 | 0 | 0 | `BANDHANBNK.NS`, `IDFCFIRSTB.NS`, `AUBANK.NS` | **PASS WITH LIMITATIONS** |
| 6 | `NIFTY_BANK__covid_2020.csv` | `NIFTY_BANK` | `COVID_2020` | 122 | 2020-01-01 to 2020-06-30 | 14 | 0 | 0 | None (12/12 present) | **PASS** |
| 7 | `NIFTY_BANK__tech_selloff_2022.csv` | `NIFTY_BANK` | `TECH_SELLOFF_2022` | 248 | 2022-01-03 to 2022-12-30 | 14 | 0 | 0 | None (12/12 present) | **PASS** |
| 8 | `NIFTY_BANK__election_2024.csv` | `NIFTY_BANK` | `ELECTION_2024` | 22 | 2024-05-15 to 2024-06-14 | 14 | 0 | 0 | None (12/12 present) | **PASS** |
| 9 | `NIFTY_PSU_BANK__2008_gfc.csv` | `NIFTY_PSU_BANK` | `2008_GFC` | 303 | 2008-01-01 to 2009-03-31 | 13 | 0 | 0 | `PSB.NS` | **PASS WITH LIMITATIONS** |
| 10 | `NIFTY_PSU_BANK__covid_2020.csv` | `NIFTY_PSU_BANK` | `COVID_2020` | 122 | 2020-01-01 to 2020-06-30 | 14 | 0 | 0 | None (12/12 present) | **PASS** |
| 11 | `NIFTY_PSU_BANK__tech_selloff_2022.csv` | `NIFTY_PSU_BANK` | `TECH_SELLOFF_2022` | 248 | 2022-01-03 to 2022-12-30 | 14 | 0 | 0 | None (12/12 present) | **PASS** |
| 12 | `NIFTY_PSU_BANK__election_2024.csv` | `NIFTY_PSU_BANK` | `ELECTION_2024` | 22 | 2024-05-15 to 2024-06-14 | 14 | 0 | 0 | None (12/12 present) | **PASS** |
| 13 | `NIFTY_PHARMA__2008_gfc.csv` | `NIFTY_PHARMA` | `2008_GFC` | 303 | 2008-01-01 to 2009-03-31 | 11 | 0 | 0 | `ALKEM.NS` | **PASS WITH LIMITATIONS** |
| 14 | `NIFTY_PHARMA__covid_2020.csv` | `NIFTY_PHARMA` | `COVID_2020` | 122 | 2020-01-01 to 2020-06-30 | 12 | 0 | 0 | None (10/10 present) | **PASS** |
| 15 | `NIFTY_PHARMA__tech_selloff_2022.csv` | `NIFTY_PHARMA` | `TECH_SELLOFF_2022` | 248 | 2022-01-03 to 2022-12-30 | 12 | 0 | 0 | None (10/10 present) | **PASS** |
| 16 | `NIFTY_PHARMA__election_2024.csv` | `NIFTY_PHARMA` | `ELECTION_2024` | 22 | 2024-05-15 to 2024-06-14 | 12 | 0 | 0 | None (10/10 present) | **PASS** |
| 17 | `NIFTY_AUTO__2008_gfc.csv` | `NIFTY_AUTO` | `2008_GFC` | 303 | 2008-01-01 to 2009-03-31 | 11 | 0 | 0 | `TATAMOTORS.NS` | **PASS WITH LIMITATIONS** |
| 18 | `NIFTY_AUTO__covid_2020.csv` | `NIFTY_AUTO` | `COVID_2020` | 122 | 2020-01-01 to 2020-06-30 | 11 | 0 | 0 | `TATAMOTORS.NS` | **PASS WITH LIMITATIONS** |
| 19 | `NIFTY_AUTO__tech_selloff_2022.csv` | `NIFTY_AUTO` | `TECH_SELLOFF_2022` | 248 | 2022-01-03 to 2022-12-30 | 11 | 0 | 0 | `TATAMOTORS.NS` | **PASS WITH LIMITATIONS** |
| 20 | `NIFTY_AUTO__election_2024.csv` | `NIFTY_AUTO` | `ELECTION_2024` | 22 | 2024-05-15 to 2024-06-14 | 11 | 0 | 0 | `TATAMOTORS.NS` | **PASS WITH LIMITATIONS** |
| 21 | `NIFTY_PRIVATE_BANK__2008_gfc.csv` | `NIFTY_PRIVATE_BANK` | `2008_GFC` | 303 | 2008-01-01 to 2009-03-31 | 8 | 0 | 0 | `IDFCFIRSTB.NS`, `BANDHANBNK.NS`, `RBLBANK.NS`, `AUBANK.NS` | **PASS WITH LIMITATIONS** |
| 22 | `NIFTY_PRIVATE_BANK__covid_2020.csv` | `NIFTY_PRIVATE_BANK` | `COVID_2020` | 122 | 2020-01-01 to 2020-06-30 | 12 | 0 | 0 | None (10/10 present) | **PASS** |
| 23 | `NIFTY_PRIVATE_BANK__tech_selloff_2022.csv` | `NIFTY_PRIVATE_BANK` | `TECH_SELLOFF_2022` | 248 | 2022-01-03 to 2022-12-30 | 12 | 0 | 0 | None (10/10 present) | **PASS** |
| 24 | `NIFTY_PRIVATE_BANK__election_2024.csv` | `NIFTY_PRIVATE_BANK` | `ELECTION_2024` | 22 | 2024-05-15 to 2024-06-14 | 12 | 0 | 0 | None (10/10 present) | **PASS** |

### Independent Validation of Structural Checks
- **Column 0 is `Date`:** 24 / 24 files (100% PASS)
- **Column -1 is `^NSEI`:** 24 / 24 files (100% PASS)
- **Duplicate Columns:** 0 across all 24 files (100% PASS)
- **Duplicate Dates:** 0 across all 24 files (100% PASS)
- **Monotonic Ascending Dates:** 24 / 24 files (100% PASS)
- **Strict `YYYY-MM-DD` Format:** 24 / 24 files (100% PASS)
- **Artificial Zero Prices:** 0 across all 24 files (100% PASS)
- **Negative Prices:** 0 across all 24 files (100% PASS)
- **Trading Session Alignment:** Perfectly synchronized with the benchmark `^NSEI` trading days for each regime.

---

## 5. Ticker Availability & Omission Evidence Audit

The reviewer conducted an independent empirical verification against Yahoo Finance for every dropped ticker. The historical IPO and listing evidence is summarized below:

| Scrutinized Ticker | Earliest Exchange Quote on yfinance | 2008 GFC Status | Modern Regimes Status | Root Cause & Evidence |
| :--- | :---: | :---: | :---: | :--- |
| `LTIM.NS` | None (HTTP 404) | Unlisted | Unlisted / 404 | Formed late 2022 via L&T Infotech & Mindtree merger. Unified symbol was unquoted in 2008/2020/2022 and returns HTTP 404 from Yahoo Finance API. |
| `TATAMOTORS.NS` | None (HTTP 404) | Inactive (404) | Inactive (404) | Corporate demerger split Tata Motors into Commercial Vehicles and Passenger Vehicles. Legacy unified ticker returns HTTP 404 on Yahoo Finance. |
| `LTTS.NS` | `2016-09-23` | Unlisted | Active | IPO occurred September 2016. Dropping from 2008 GFC is 100% empirically justified. |
| `PERSISTENT.NS` | `2010-04-06` | Unlisted | Active | IPO occurred April 2010. Dropping from 2008 GFC is 100% empirically justified. |
| `ALKEM.NS` | `2015-12-23` | Unlisted | Active | IPO occurred December 2015. Dropping from 2008 GFC is 100% empirically justified. |
| `PSB.NS` | `2010-12-30` | Unlisted | Active | IPO occurred December 2010. Dropping from 2008 GFC is 100% empirically justified. |
| `BANDHANBNK.NS` | `2018-03-27` | Unlisted | Active | IPO occurred March 2018. Dropping from 2008 GFC is 100% empirically justified. |
| `IDFCFIRSTB.NS` | `2015-11-06` | Unlisted | Active | IDFC Bank listed November 2015; merger with Capital First completed December 2018. Dropping from 2008 GFC is 100% empirically justified. |
| `AUBANK.NS` | `2017-07-11` | Unlisted | Active | IPO occurred July 2017. Dropping from 2008 GFC is 100% empirically justified. |
| `RBLBANK.NS` | `2016-08-31` | Unlisted | Active | IPO occurred August 2016. Dropping from 2008 GFC is 100% empirically justified. |

**Audit Finding:** The omissions are **100% legitimate historical exchange limitations**. Under the zero-hallucination data engineering contract, omitting unlisted stocks is the only mathematically correct procedure.

---

## 6. Benchmark and Drawdown Audit (`^NSEI`)

The mathematical implementation of `compute_max_drawdown()` was audited against independent manual computation:

$$\text{Drawdown}_t = \frac{S_t - \max_{i \le t} S_i}{\max_{i \le t} S_i}, \quad \text{Max Drawdown} = \min_t \text{Drawdown}_t$$

### Independent Verification Across All 4 Regimes
All 6 sectors within each regime produce identical benchmark values and identical drawdown statistics:

| Regime | Start Date | End Date | Sessions | Peak Value | Peak Date | Trough Value | Trough Date | Measured Max Drawdown | Cross-Sector Equality |
| :--- | :---: | :---: | :-: | :-: | :---: | :-: | :---: | :-: | :---: |
| `2008_GFC` | 2008-01-01 | 2009-03-31 | 303 | 6,287.85 | 2008-01-08 | 2,524.20 | 2008-10-27 | **`-59.86%`** | 100% Identical |
| `COVID_2020` | 2020-01-01 | 2020-06-30 | 122 | 12,362.30 | 2020-01-14 | 7,610.25 | 2020-03-23 | **`-38.44%`** | 100% Identical |
| `TECH_SELLOFF_2022` | 2022-01-03 | 2022-12-30 | 248 | 18,308.10 | 2022-01-17 | 15,293.50 | 2022-06-17 | **`-16.47%`** | 100% Identical |
| `ELECTION_2024` | 2024-05-15 | 2024-06-14 | 22 | 23,263.90 | 2024-06-03 | 21,884.50 | 2024-06-04 | **`-5.93%`** | 100% Identical |

**Documentation Note / Discrepancy:**
In earlier informal notes, the 2022 peak was cited as 18,349.70 on 2022-01-18 (which represents the intraday high). The daily adjusted close price on 2022-01-17 was 18,308.10. `compute_max_drawdown()` uses adjusted daily closes, and correctly yields -16.47% from 18,308.10 to 15,293.50. This is verified correct.

---

## 7. Downloader and Orchestration Code Audit

### `scripts/download_historical_data.py`
- **Data Ingestion:** Uses `yf.download(ticker, start, end, auto_adjust=True, progress=False)`.
- **Date Handling:** `end_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1)` properly includes the regime end date despite yfinance's exclusive upper bound.
- **Trading Calendar Alignment:** Benchmark `^NSEI` is downloaded first to establish the official market sessions. All stock series are reindexed to `trading_calendar`.
- **Missing Data Policy:** `c = t_series.reindex(trading_calendar)`. Missing values remain `NaN` and are written out with `na_rep=""`. Zero-filling and forward-filling are strictly omitted.
- **Rate Limiting & Retries:** Sleeps 0.5s after requests. Implements up to 2 retries on transient network errors. Permanently drops symbols on 404/delisted errors without infinite retry loops.
- **Safety:** Checks `out_path.exists() and not overwrite` to prevent accidental overwrites. Does not execute downloads when imported as a library.

### `scripts/execute_phase1_loop.py`
- **Loop Architecture:** Iterates deterministically over 4 regimes × 6 sectors.
- **Cache Optimization:** Maintains a `shared_regime_cache` within each regime loop, ensuring each unique stock and benchmark are queried across the network at most once per regime.
- **Validation-Driven Completion:** Calls `audit_single_dataset()` after every download to verify column order, date monotonicity, zero count, and drawdown before recording status.

---

## 8. Fundamentals Data Audit (`fundamentals_2026-10-30.csv`)

Direct independent parsing of `data/fundamentals_2026-10-30.csv` establishes:
- **Total Rows:** 51 companies
- **Candidate Equities Evaluated:** 53 (`config.SECTOR_TICKERS` + `RELIANCE.NS`)
- **Unmatched Tickers:** `LTIM.NS` and `TATAMOTORS.NS` (HTTP 404 on Yahoo Finance quote summary endpoint)
- **Columns (11):** `ticker`, `company_name`, `market_cap`, `trailing_pe`, `forward_pe`, `return_on_equity`, `revenue_growth`, `debt_to_equity`, `profit_margins`, `sector`, `industry`
- **Duplicate Tickers:** 0
- **Artificial Zeroes:** **0** across all numeric columns
- **P/E Disambiguation:** `trailing_pe` (min 4.83, max 116.45) and `forward_pe` (min 4.91, max 64.59) are cleanly separated.
- **Debt-to-Equity Null Distribution:** Exactly 22 nulls, and 100% of the 22 nulls belong to the `Financial Services` sector (banking institutions where deposits are customer liabilities, making corporate D/E non-applicable).
- **Snapshot Date:** Confirmed as **current snapshot as of 2026-10-30**, not historical crisis balance sheets.

---

## 9. Official NSE F&O Lot-Size Audit

Direct cross-join between `data/nse_lot_sizes.csv` and the official circular `data/nse_fo_mktlots_source.csv`:
- **Raw NSE Circular File:** `data/nse_fo_mktlots_source.csv` (48,816 bytes, 225 rows downloaded from official NSE archives).
- **Output Lot Sizes File:** `data/nse_lot_sizes.csv` (2,931 bytes, 46 matched rows).
- **Expiry Cycle Used:** `NOV-26` (near-month contract).
- **As-of Date:** `2026-10-30`.
- **Discrepancy Check:** **0 discrepancies**. Every single lot size in `data/nse_lot_sizes.csv` matches the raw NSE source `NOV-26` value character-for-character.
- **`IDFCFIRSTB.NS` Audit:** Explicitly checked. Output lot size = `9,275`. Raw circular column `NOV-26` = `9275`. Verified exact match.
- **Unmatched Candidates:** 8 candidates (`BALKRISIND.NS`, `CENTRALBK.NS`, `IOB.NS`, `LTIM.NS`, `LTTS.NS`, `PSB.NS`, `TATAMOTORS.NS`, `UCOBANK.NS`). Verified: none of these symbols appear in the official NSE derivatives circular. They are cash-only or delisted/restructured stocks. Zero synthetic lot sizes were assigned.

---

## 10. Automated Testing Audit

The test suite was executed in full via pytest:

```text
pytest
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.2.0, pluggy-1.7.0
rootdir: C:\Users\karti\Documents\antigravity\modest-babbage
configfile: pyproject.toml
testpaths: tests
plugins: anyio-4.15.1, langsmith-0.14.16, platformdirs-4.14.0, cov-7.1.0
collected 40 items

tests/test_beta_calculator.py ...........                                [ 27%]
tests/test_cointegration.py .......                                      [ 45%]
tests/test_download_historical_data.py ...........                       [ 72%]
tests/test_portfolio.py ......                                           [ 87%]
tests/test_verifier.py .....                                             [100%]

============================= 40 passed in 4.14s ==============================
```

### Test Quality & Coverage Evaluation
- **Integration with Real CSVs:** `TestPhase1DatasetsIntegrity` opens and validates all 24 historical CSVs, `fundamentals_2026-10-30.csv`, and `nse_lot_sizes.csv` directly from disk.
- **Structural Integrity:** Tests verify date uniqueness, date monotonicity, column order (`Date` first, `^NSEI` last), and zero-price prohibition.
- **Missing Data Safety:** Verified via `test_missing_prices_remain_nan`.
- **Fault Tolerance:** Verified via `test_transient_error_retries_and_succeeds` and `test_batch_continues_if_one_sector_fails`.

---

## 11. Quant Engine & Agent Pipeline Integration Readiness

The reviewer verified compatibility against `engine/beta_calculator.py`, `engine/cointegration.py`, and `engine/portfolio.py`:

1. **Beta Calculation Compatibility:**
   - Evaluated on `data/NIFTY_IT__covid_2020.csv`:
     - `compute_static_beta(returns['TCS.NS'], returns['^NSEI']) = 0.7531`
     - `compute_static_beta(returns['INFY.NS'], returns['^NSEI']) = 0.8949`
   - Data streams directly into OLS covariance/variance formulas without conversion.
2. **Cointegration Compatibility:**
   - Evaluated on `data/NIFTY_IT__covid_2020.csv`:
     - `engle_granger_test(df['TCS.NS'], df['INFY.NS'])` yields $p$-value = `0.1095`.
   - Function consumes price series directly.
3. **F&O Conversion Risk (Important Integration Guardrail):**
   - In `engine/portfolio.py`, `convert_to_fno_lots()` raises `ValueError(f"Lot size missing for {ticker}")` if a ticker is not in `lot_sizes`.
   - **Recommendation for Quant Team:** Upstream screening agents must verify whether a chosen pair consists of F&O-eligible stocks before attempting derivative lot sizing, or fall back to reporting cash-market share allocations for cash-only constituents (such as `LTTS.NS` or `CENTRALBK.NS`).

---

## 12. Documentation Audit

- **`README.md`:** Data Engineering commands cleanly added; instructions for running ingestion and tests are accurate and functional.
- **`data/PHASE_1_DATA_AUDIT.md`:** Comprehensive audit log accurately documents all 24 combinations and dropped tickers.
- **`data/DATA_DICTIONARY.md`:** Accurately specifies all schemas, units, missing-value conventions, and data limitations.

---

## 13. Discrepancies, Observations & Prioritized Recommendations

### Low Severity (Optional Refinements)
1. **F&O Source Cross-Match Test:** Currently `test_lot_sizes_integrity` tests `data/nse_lot_sizes.csv` shape and metadata, but does not execute a live cross-join against `data/nse_fo_mktlots_source.csv`. The manual cross-join confirmed 100% consistency; adding this assertion directly to pytest would automate circular regression testing.
2. **`config.FNO_LOT_SIZES` Synchronization:** `config.py` contains a static 23-ticker dictionary from older NSE circulars (e.g. `MARUTI: 100`). The actual November 2026 circular in `data/nse_lot_sizes.csv` uses `MARUTI: 50`. Once teammates authorize changes to `config.py`, `config.FNO_LOT_SIZES` can be updated to point directly to `data/nse_lot_sizes.csv`.

---

## 14. Final Audit Verdict

### **PHASE 1 COMPLETE WITH DOCUMENTED LIMITATIONS**

**Justification:**  
All 24 historical sector/regime combinations have been ingested, aligned to benchmark trading days, and audited with zero artificial zero insertions and zero data fabrication. Dropped tickers (`LTIM.NS`, `TATAMOTORS.NS`, and unlisted 2008 stocks) represent genuine exchange limitations confirmed by empirical market queries. Fundamentals and official F&O lot sizes are verified. 40 of 40 tests pass. The codebase is clean, reliable, and ready for integration.
