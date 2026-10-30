# StocX — Phase 1 Comprehensive Data Engineering Audit Report

**Role:** Data Engineer (`anaytiwari/data`)  
**Reporting To:** Tanush (Lead / Quant Teammate)  
**Date:** 2026-10-30  
**Status:** **PHASE 1 COMPLETE (24 of 24 Historical Datasets Ingested & Verified)**  

---

## 1. Executive Summary & Scope
This document certifies the successful completion of Phase 1 Data Engineering responsibilities for the StocX Market-Neutral Hedge Builder. All 24 historical sector/regime combinations (6 configured NSE sectors × 4 historical stress regimes), company fundamentals, and official NSE F&O lot sizes have been ingested, standardized, audited, and verified against strict zero-hallucination guardrails.

**Core Data Contract Rules:**
- Column 0 is strictly `Date` (formatted `YYYY-MM-DD`, unique, ascending).
- Final column is strictly the benchmark `^NSEI`.
- Missing observations are preserved as `NaN` / empty strings `,`, never filled with `0.0`, forward-filled, or synthetically fabricated.
- All historical stock prices represent split- and dividend-adjusted closing prices.
- Delisted, merged, or pre-IPO tickers are dropped with transparent, documented justifications.

---

## 2. Master Historical Dataset Completion Matrix (6 Sectors × 4 Regimes)

| Sector | COVID_2020 | ELECTION_2024 | TECH_SELLOFF_2022 | 2008_GFC |
| :--- | :---: | :---: | :---: | :---: |
| **`NIFTY_IT`** | **PASS WITH LIMITATIONS** | **PASS WITH LIMITATIONS** | **PASS WITH LIMITATIONS** | **PASS WITH LIMITATIONS** |
| **`NIFTY_BANK`** | **PASS** | **PASS** | **PASS** | **PASS WITH LIMITATIONS** |
| **`NIFTY_AUTO`** | **PASS WITH LIMITATIONS** | **PASS WITH LIMITATIONS** | **PASS WITH LIMITATIONS** | **PASS WITH LIMITATIONS** |
| **`NIFTY_PHARMA`** | **PASS** | **PASS** | **PASS** | **PASS WITH LIMITATIONS** |
| **`NIFTY_PSU_BANK`** | **PASS** | **PASS** | **PASS** | **PASS WITH LIMITATIONS** |
| **`NIFTY_PRIVATE_BANK`** | **PASS** | **PASS** | **PASS** | **PASS WITH LIMITATIONS** |

> **Status Legend:**
> - **PASS**: All configured sector constituents and benchmark successfully retrieved with 100% full trading history.
> - **PASS WITH LIMITATIONS**: Successfully ingested with documented omissions due to pre-IPO status, corporate demergers, or legacy ticker deactivations.
> - **BLOCKED**: 0 datasets blocked. All 24 datasets operational.

---

## 3. Detailed Audit of All 24 Historical Datasets

| # | Dataset File | Sector | Regime | Trading Days | Constituents | Retained / Config | Nulls | Zeroes | Max Drawdown | Verdict |
| :-: | :--- | :--- | :--- | :-: | :-: | :-: | :-: | :-: | :-: | :---: |
| 1 | [`NIFTY_IT__covid_2020.csv`](NIFTY_IT__covid_2020.csv) | `NIFTY_IT` | `COVID_2020` | 122 | 9 | 9/10 | 0 | 0 | -38.44% | PASS WITH LIMITATIONS |
| 2 | [`NIFTY_BANK__covid_2020.csv`](NIFTY_BANK__covid_2020.csv) | `NIFTY_BANK` | `COVID_2020` | 122 | 12 | 12/12 | 0 | 0 | -38.44% | PASS |
| 3 | [`NIFTY_AUTO__covid_2020.csv`](NIFTY_AUTO__covid_2020.csv) | `NIFTY_AUTO` | `COVID_2020` | 122 | 9 | 9/10 | 0 | 0 | -38.44% | PASS WITH LIMITATIONS |
| 4 | [`NIFTY_PHARMA__covid_2020.csv`](NIFTY_PHARMA__covid_2020.csv) | `NIFTY_PHARMA` | `COVID_2020` | 122 | 10 | 10/10 | 0 | 0 | -38.44% | PASS |
| 5 | [`NIFTY_PSU_BANK__covid_2020.csv`](NIFTY_PSU_BANK__covid_2020.csv) | `NIFTY_PSU_BANK` | `COVID_2020` | 122 | 12 | 12/12 | 0 | 0 | -38.44% | PASS |
| 6 | [`NIFTY_PRIVATE_BANK__covid_2020.csv`](NIFTY_PRIVATE_BANK__covid_2020.csv) | `NIFTY_PRIVATE_BANK` | `COVID_2020` | 122 | 10 | 10/10 | 0 | 0 | -38.44% | PASS |
| 7 | [`NIFTY_IT__election_2024.csv`](NIFTY_IT__election_2024.csv) | `NIFTY_IT` | `ELECTION_2024` | 22 | 9 | 9/10 | 0 | 0 | -5.93% | PASS WITH LIMITATIONS |
| 8 | [`NIFTY_BANK__election_2024.csv`](NIFTY_BANK__election_2024.csv) | `NIFTY_BANK` | `ELECTION_2024` | 22 | 12 | 12/12 | 0 | 0 | -5.93% | PASS |
| 9 | [`NIFTY_AUTO__election_2024.csv`](NIFTY_AUTO__election_2024.csv) | `NIFTY_AUTO` | `ELECTION_2024` | 22 | 9 | 9/10 | 0 | 0 | -5.93% | PASS WITH LIMITATIONS |
| 10 | [`NIFTY_PHARMA__election_2024.csv`](NIFTY_PHARMA__election_2024.csv) | `NIFTY_PHARMA` | `ELECTION_2024` | 22 | 10 | 10/10 | 0 | 0 | -5.93% | PASS |
| 11 | [`NIFTY_PSU_BANK__election_2024.csv`](NIFTY_PSU_BANK__election_2024.csv) | `NIFTY_PSU_BANK` | `ELECTION_2024` | 22 | 12 | 12/12 | 0 | 0 | -5.93% | PASS |
| 12 | [`NIFTY_PRIVATE_BANK__election_2024.csv`](NIFTY_PRIVATE_BANK__election_2024.csv) | `NIFTY_PRIVATE_BANK` | `ELECTION_2024` | 22 | 10 | 10/10 | 0 | 0 | -5.93% | PASS |
| 13 | [`NIFTY_IT__tech_selloff_2022.csv`](NIFTY_IT__tech_selloff_2022.csv) | `NIFTY_IT` | `TECH_SELLOFF_2022` | 248 | 9 | 9/10 | 0 | 0 | -16.47% | PASS WITH LIMITATIONS |
| 14 | [`NIFTY_BANK__tech_selloff_2022.csv`](NIFTY_BANK__tech_selloff_2022.csv) | `NIFTY_BANK` | `TECH_SELLOFF_2022` | 248 | 12 | 12/12 | 0 | 0 | -16.47% | PASS |
| 15 | [`NIFTY_AUTO__tech_selloff_2022.csv`](NIFTY_AUTO__tech_selloff_2022.csv) | `NIFTY_AUTO` | `TECH_SELLOFF_2022` | 248 | 9 | 9/10 | 0 | 0 | -16.47% | PASS WITH LIMITATIONS |
| 16 | [`NIFTY_PHARMA__tech_selloff_2022.csv`](NIFTY_PHARMA__tech_selloff_2022.csv) | `NIFTY_PHARMA` | `TECH_SELLOFF_2022` | 248 | 10 | 10/10 | 0 | 0 | -16.47% | PASS |
| 17 | [`NIFTY_PSU_BANK__tech_selloff_2022.csv`](NIFTY_PSU_BANK__tech_selloff_2022.csv) | `NIFTY_PSU_BANK` | `TECH_SELLOFF_2022` | 248 | 12 | 12/12 | 0 | 0 | -16.47% | PASS |
| 18 | [`NIFTY_PRIVATE_BANK__tech_selloff_2022.csv`](NIFTY_PRIVATE_BANK__tech_selloff_2022.csv) | `NIFTY_PRIVATE_BANK` | `TECH_SELLOFF_2022` | 248 | 10 | 10/10 | 0 | 0 | -16.47% | PASS |
| 19 | [`NIFTY_IT__2008_gfc.csv`](NIFTY_IT__2008_gfc.csv) | `NIFTY_IT` | `2008_GFC` | 303 | 7 | 7/10 | 0 | 0 | -59.86% | PASS WITH LIMITATIONS |
| 20 | [`NIFTY_BANK__2008_gfc.csv`](NIFTY_BANK__2008_gfc.csv) | `NIFTY_BANK` | `2008_GFC` | 303 | 9 | 9/12 | 0 | 0 | -59.86% | PASS WITH LIMITATIONS |
| 21 | [`NIFTY_AUTO__2008_gfc.csv`](NIFTY_AUTO__2008_gfc.csv) | `NIFTY_AUTO` | `2008_GFC` | 303 | 9 | 9/10 | 0 | 0 | -59.86% | PASS WITH LIMITATIONS |
| 22 | [`NIFTY_PHARMA__2008_gfc.csv`](NIFTY_PHARMA__2008_gfc.csv) | `NIFTY_PHARMA` | `2008_GFC` | 303 | 9 | 9/10 | 0 | 0 | -59.86% | PASS WITH LIMITATIONS |
| 23 | [`NIFTY_PSU_BANK__2008_gfc.csv`](NIFTY_PSU_BANK__2008_gfc.csv) | `NIFTY_PSU_BANK` | `2008_GFC` | 303 | 11 | 11/12 | 0 | 0 | -59.86% | PASS WITH LIMITATIONS |
| 24 | [`NIFTY_PRIVATE_BANK__2008_gfc.csv`](NIFTY_PRIVATE_BANK__2008_gfc.csv) | `NIFTY_PRIVATE_BANK` | `2008_GFC` | 303 | 6 | 6/10 | 0 | 0 | -59.86% | PASS WITH LIMITATIONS |

---

## 4. Benchmark Drawdown Validation across Regimes (`^NSEI`)

Benchmark prices (`^NSEI`) establish the active NSE trading calendar and validate crisis dynamics:

| Regime | Date Range | Sessions | Benchmark Peak | Peak Date | Benchmark Trough | Trough Date | Max Drawdown | Crisis Captured? |
| :--- | :---: | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| **`COVID_2020`** | 2020-01-01 to 2020-06-30 | 122 | 12362.30 | 2020-01-14 | 7610.25 | 2020-03-23 | -38.44% | Yes |
| **`ELECTION_2024`** | 2024-05-15 to 2024-06-14 | 22 | 23263.90 | 2024-06-03 | 21884.50 | 2024-06-04 | -5.93% | Yes (Short Shock) |
| **`TECH_SELLOFF_2022`** | 2022-01-03 to 2022-12-30 | 248 | 18308.10 | 2022-01-17 | 15293.50 | 2022-06-17 | -16.47% | Yes |
| **`2008_GFC`** | 2008-01-01 to 2009-03-31 | 303 | 6287.85 | 2008-01-08 | 2524.20 | 2008-10-27 | -59.86% | Yes |

---

## 5. Ticker Coverage & Transparent Omission Log

Under the StocX Data Contract, missing historical tickers are never synthetically simulated. The following omissions reflect genuine exchange history:

| Sector | Regime | Dropped Ticker | Underlying Cause & Evidence | Downstream Mitigation |
| :--- | :--- | :--- | :--- | :--- |
| `NIFTY_IT` | All 4 Regimes | `LTIM.NS` | Formed late 2022 via L&T Infotech & Mindtree merger. Unified symbol was unquoted in earlier windows and returns 404 on current quote summary. | Sector hedge uses remaining 9 liquid constituents (`TCS`, `INFY`, `HCLTECH`, `WIPRO`, etc.). |
| `NIFTY_AUTO` | All 4 Regimes | `TATAMOTORS.NS` | Corporate demerger split entity into Commercial (`TMCV`) and Passenger (`TMPV`). Legacy unified ticker inactive (404) on Yahoo Finance. | Sector hedge uses 9 liquid auto constituents (`MARUTI`, `M&M`, `BAJAJ-AUTO`, `HEROMOTOCO`, etc.). |
| `NIFTY_IT` | `2008_GFC` | `LTTS.NS` | L&T Technology Services IPO occurred in September 2016. No exchange price data in 2008. | Correctly dropped from 2008 GFC backtests. |
| `NIFTY_IT` | `2008_GFC` | `PERSISTENT.NS` | Persistent Systems IPO occurred in March 2010. | Correctly dropped from 2008 GFC backtests. |
| `NIFTY_BANK` / `NIFTY_PRIVATE_BANK` | `2008_GFC` | `BANDHANBNK.NS` | Bandhan Bank IPO occurred in March 2018. | Correctly dropped from 2008 GFC backtests. |
| `NIFTY_BANK` / `NIFTY_PRIVATE_BANK` | `2008_GFC` | `IDFCFIRSTB.NS` | IDFC Bank listed late 2015; merger with Capital First completed December 2018. | Correctly dropped from 2008 GFC backtests. |
| `NIFTY_BANK` / `NIFTY_PRIVATE_BANK` | `2008_GFC` | `AUBANK.NS` | AU Small Finance Bank IPO occurred in June 2017. | Correctly dropped from 2008 GFC backtests. |
| `NIFTY_PRIVATE_BANK` | `2008_GFC` | `RBLBANK.NS` | RBL Bank IPO occurred in August 2016. | Correctly dropped from 2008 GFC backtests. |
| `NIFTY_PHARMA` | `2008_GFC` | `ALKEM.NS` | Alkem Laboratories IPO occurred in December 2015. | Correctly dropped from 2008 GFC backtests. |
| `NIFTY_PSU_BANK` | `2008_GFC` | `PSB.NS` | Punjab & Sind Bank IPO occurred in December 2010. | Correctly dropped from 2008 GFC backtests. |

---

## 6. Company Fundamentals Re-Audit (`fundamentals_2026-10-30.csv`)

- **File Path:** `data/fundamentals_2026-10-30.csv` (6,895 bytes)
- **Coverage:** 51 / 53 candidate tickers (96.2% coverage).
- **Omissions:** `LTIM.NS` and `TATAMOTORS.NS` (HTTP 404 on current quote summary endpoint).
- **Schema (11 columns):** `ticker`, `company_name`, `market_cap`, `trailing_pe`, `forward_pe`, `return_on_equity`, `revenue_growth`, `debt_to_equity`, `profit_margins`, `sector`, `industry`.
- **P/E Ratio Disambiguation:** `trailing_pe` and `forward_pe` are independently populated without cross-contamination.
- **Zero-Substitution Invariant:** Verified **0 artificial zeroes**. Missing values remain blank commas `,` (e.g. 22 banking firms omit D/E per financial industry convention).
- **Point-in-Time Distinction:** Represents **current fundamental snapshot as of 2026-10-30** for live pair screening; historical stress testing relies exclusively on historical price series.

---

## 7. Official NSE F&O Lot Sizes Re-Audit (`nse_lot_sizes.csv`)

- **File Path:** `data/nse_lot_sizes.csv` (2,931 bytes)
- **Source File:** `data/nse_fo_mktlots_source.csv` (48,816 bytes, raw CSV downloaded directly from NSE Archives).
- **Coverage:** 46 matched active F&O tickers.
- **Expiry:** `NOV-26` (near-month contract).
- **As-of Date:** `2026-10-30`.
- **Lot Size Range:** Min 50 (`MARUTI.NS`), Max 9,275 (`IDFCFIRSTB.NS`). 100% positive integers.
- **Cash vs. F&O Segmentation:** 7 configured tickers do not trade in F&O (`LTTS`, `CENTRALBK`, `IOB`, `MAHABANK`, `PSB`, `UCOBANK`, `CANBK` cash-only or dropped). `engine/portfolio.py` safely handles cash-only stocks.

---

## 8. Cross-Dataset Consistency Findings

1. **Schema Uniformity:** 100% of the 24 historical CSV files follow the exact same column ordering: `Date` first, constituent ticker columns alphabetically sorted or config-ordered, `^NSEI` strictly final.
2. **Calendar Alignment:** Every ticker column is reindexed strictly to the benchmark trading calendar for that regime. Days where trading was halted or unavailable remain strictly `NaN` without forward filling.
3. **Naming Convention:** All historical filenames match `data/<SECTOR>__<regime_lower>.csv` without exception.
4. **Zero-Hallucination Guarantee:** Total zeroes across all price columns across all 24 datasets: **0**.

---

## 9. Test Suite Verification & Git Safety

- **Pytest Suite:** **40 passed, 0 failed** across all test modules:
  - `tests/test_download_historical_data.py`: 11 passed (regime-agnostic drawdown, NaN policy, retries, 404 bypass, error isolation, overwrite protection, 24-file existence, 24-file schema, fundamentals integrity, lot-size integrity).
  - `tests/test_beta_calculator.py`: 11 passed.
  - `tests/test_cointegration.py`: 7 passed.
  - `tests/test_portfolio.py`: 6 passed.
  - `tests/test_verifier.py`: 5 passed.
- **Active Branch:** `anaytiwari/data` (clean tracking of `origin/main`).
- **Git Protection Invariants:** Zero commits, zero pushes, zero modifications to teammate modules (`config.py`, `engine/*`, `agents/*`, `ui/*`). `.env` and `.venv/` remain strictly ignored.

---

### Phase 1 Sign-Off Verdict: **PHASE 1 COMPLETE (READY FOR QUANT PAIR ENGINE)**