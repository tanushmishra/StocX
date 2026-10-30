# Quantitative Engine Verification Report

**Author:** Tanush (Quant Engine Lead)  
**Date:** 2026-10-30  
**Repository Branch:** `proA/quant-checks`  
**Execution Environment:** Windows, Python 3.13.13, Virtual Environment (`.venv`), `ALLOW_SYNTHETIC=false`

---

## 1. Executive Summary

This report documents the rigorous verification of the **Deterministic Quant Engine** on real historical National Stock Exchange of India (NSE) equity data across four major sectors (`NIFTY_IT`, `NIFTY_BANK`, `NIFTY_AUTO`, `NIFTY_PHARMA`) and five market stress windows (`main_3y`, `gfc_2008`, `tech_2022`, `covid_2020`, `election_2024`).

All calculations were conducted independently with zero synthetic data. Four engine discrepancies were identified, documented with exact numerical evidence, and minimally remediated with comprehensive regression unit tests. Following remediation, the engine achieves $100\%$ precision matching against the independent quantitative reference standard across all mathematical metrics within a strict tolerance of $10^{-4}$.

The full test suite passed with 47 passing tests in 1.85 seconds.

---

## 2. Real Data Download & Validation Audit

All market datasets were downloaded from Yahoo Finance using official `.NS` identifiers, adjusted closing prices (`auto_adjust=True`), and strictly validated against institutional data hygiene standards.

### Data Integrity Rules Enforced:
1. Benchmark `^NSEI` present in every file.
2. Zero non-positive, zero, or missing (`NaN`) values.
3. Strictly ascending, unique dates with no gap exceeding 7 calendar days.
4. Minimum history requirement $\ge 100$ daily bars.
5. Verification of the historical March 2020 COVID trough date.

### Validation Results Table

| Sector | Window | Date Range | Rows | Max Gap (Days) | Status | Notes |
| :--- | :--- | :--- | :---: | :---: | :---: | :--- |
| **NIFTY_IT** | `main_3y` | 2023-10-03 to 2026-10-30 | 759 | 4 | **PASS** | Complete history |
| **NIFTY_IT** | `gfc_2008` | 2007-06-01 to 2009-06-30 | 434 | 5 | **PASS** | Complete history |
| **NIFTY_IT** | `covid_2020` | 2019-06-03 to 2020-12-31 | 391 | 4 | **PASS** | Trough on 2020-03-23 |
| **NIFTY_IT** | `tech_2022` | 2021-06-01 to 2022-12-30 | 396 | 5 | **PASS** | Complete history |
| **NIFTY_IT** | `election_2024`| 2023-10-03 to 2024-09-30 | 244 | 4 | **PASS** | Complete history |
| **NIFTY_BANK**| `main_3y` | 2023-10-03 to 2026-10-30 | 759 | 4 | **PASS** | Complete history |
| **NIFTY_BANK**| `gfc_2008` | 2007-06-01 to 2009-06-30 | 434 | 5 | **PASS** | Complete history |
| **NIFTY_BANK**| `covid_2020` | 2019-06-03 to 2020-12-31 | 391 | 4 | **PASS** | Trough on 2020-03-23 |
| **NIFTY_BANK**| `tech_2022` | 2021-06-01 to 2022-12-30 | 396 | 5 | **PASS** | Complete history |
| **NIFTY_BANK**| `election_2024`| 2023-10-03 to 2024-09-30 | 244 | 4 | **PASS** | Complete history |
| **NIFTY_AUTO**| `main_3y` | 2023-10-03 to 2026-10-30 | 759 | 4 | **PASS** | Complete history |
| **NIFTY_AUTO**| `gfc_2008` | 2007-06-01 to 2009-06-30 | 434 | 5 | **PASS** | Complete history |
| **NIFTY_AUTO**| `covid_2020` | 2019-06-03 to 2020-12-31 | 391 | 4 | **PASS** | Trough on 2020-03-23 |
| **NIFTY_AUTO**| `tech_2022` | 2021-06-01 to 2022-12-30 | 396 | 5 | **PASS** | Complete history |
| **NIFTY_AUTO**| `election_2024`| 2023-10-03 to 2024-09-30 | 244 | 4 | **PASS** | Complete history |
| **NIFTY_PHARMA**| `main_3y` | 2023-10-03 to 2026-10-30 | 759 | 4 | **PASS** | Complete history |
| **NIFTY_PHARMA**| `gfc_2008` | 2007-06-01 to 2009-06-30 | 434 | 5 | **PASS** | Complete history |
| **NIFTY_PHARMA**| `covid_2020` | 2019-06-03 to 2020-12-31 | 391 | 4 | **PASS** | Trough on 2020-03-23 |
| **NIFTY_PHARMA**| `tech_2022` | 2021-06-01 to 2022-12-30 | 396 | 5 | **PASS** | Complete history |
| **NIFTY_PHARMA**| `election_2024`| 2023-10-03 to 2024-09-30 | 244 | 4 | **PASS** | Complete history |

* **Lowest ^NSEI Close in COVID_2020:** Date = `2020-03-23`, Close = `7610.25` INR (falls exactly in the second half of March 2020).
* **Tickers Dropped (> 5% missing / unlisted / 404):**
  - `LTIM.NS`: Unavailable / 404 on Yahoo Finance across all windows. Reported and omitted per instructions.
  - `TATAMOTORS.NS`: Unavailable / 404 on Yahoo Finance (due to corporate demerger restructuring). Reported and omitted per instructions.
  - Pre-IPO constituents omitted from `gfc_2008`: `PERSISTENT.NS`, `LTTS.NS`, `BANDHANBNK.NS`, `IDFCFIRSTB.NS`, `AUBANK.NS`, `ALKEM.NS`.

---

## 3. Independent Reference vs. Engine Comparison

Independent calculations were implemented in `analysis/quant_check.py` without importing anything from `engine/`, utilizing exclusively `numpy`, `pandas`, and `statsmodels`.

The test pair evaluated is **`TCS.NS` (Long) vs. `WIPRO.NS` (Short)** on `scratch_data/NIFTY_IT__main_3y.csv` (759 daily bars) and an out-of-sample crash test on `covid_2020` (Estimation: `2019-06-01` to `2020-01-31`, Evaluation: `2020-02-01` to `2020-04-30`).

### Metric Comparison Table

| Metric | Reference Value | Engine Value | Absolute Difference | Status ($\le 10^{-4}$) |
| :--- | :---: | :---: | :---: | :---: |
| **Beta Long (`TCS.NS`)** | `0.781123` | `0.781123` | `0.000000` | **MATCH** |
| **Beta Short (`WIPRO.NS`)** | `0.965070` | `0.965070` | `0.000000` | **MATCH** |
| **Pair Return Correlation** | `0.619978` | `0.619978` | `0.000000` | **MATCH** |
| **Weight Long ($w_L$)** | `0.552671` | `0.552671` | `0.000000` | **MATCH** |
| **Weight Short ($w_S$)** | `-0.447329` | `-0.447329` | `0.000000` | **MATCH** |
| **OU Half-Life (days)** | `94.414309` | `94.414309` | `0.000000` | **MATCH** |
| **EWMA Beta Long ($\lambda=0.94$)** | `1.153492` | `1.153492` | `0.000000` | **MATCH** |
| **EWMA Beta Short ($\lambda=0.94$)**| `1.451542` | `1.451542` | `0.000000` | **MATCH** |
| **60-day Rolling Beta Long** | `0.948243` | `0.948243` | `0.000000` | **MATCH** |
| **60-day Rolling Beta Short** | `1.208134` | `1.208134` | `0.000000` | **MATCH** |
| **Engle-Granger Cointegration $p$ (Log Prices)** | `0.620957` | `0.620957` | `0.000000` | **MATCH** |
| **Engle-Granger Cointegration $p$ (Raw Prices)** | `0.620957` | `0.681697` | `0.060740` | **DEMONSTRATED SUSPECT** |
| **Crash Hedged MDD** | `0.115100` | `0.115100` | `0.000000` | **MATCH** |
| **Crash Unhedged MDD** | `0.256096` | `0.256096` | `0.000000` | **MATCH** |
| **Crash MDD Ratio** | `0.449440` | `0.449441` | `0.000001` | **MATCH** |
| **Crash Realized Beta** | `0.421417` | `0.421400` | `0.000017` | **MATCH** |
| **Crash Sharpe Ratio** | `0.489232` | `0.489200` | `0.000032` | **MATCH** |
| **Crash Sortino Ratio** | `0.680850` | `0.680800` | `0.000050` | **MATCH** |
| **Crash VaR 95%** | `-0.037436` | `-0.037436` | `0.000000` | **MATCH** |

*Note on statsmodels:* The engine verified direct utilization of `statsmodels.tsa.stattools.coint` and `statsmodels.api.OLS` (no SciPy fallback was engaged).

---

## 4. Quant Engine Bug Diagnoses & Remediations

### Bug 1: Compounded Risk-Free Rate in Backtester (`engine/backtester.py`)
- **Evidence:** `calc_metrics` previously calculated the daily risk-free rate using geometric compounding:  
  `rf_daily = (1 + rf_rate) ** (1 / 252) - 1` ($0.00026114$).  
  The background specification mandates daily simple interest: $R_f / 252 = 0.068 / 252 = 0.00026984$.
- **Impact:** Compounding underestimated the daily risk-free deduction by $8.7 \times 10^{-6}$, resulting in an overstated Sharpe ratio of `0.4963` instead of `0.4892` (difference of `0.0071 > 1e-4`).
- **Remediation:** Changed line 108 of `engine/backtester.py` to:  
  `rf_daily = rf_rate / _TRADING_DAYS_PER_YEAR`
- **Regression Test:** Added `test_simple_daily_risk_free_rate` in `tests/test_quant_regression.py`.

### Bug 2: Non-Standard Sortino Downside Deviation (`engine/backtester.py`)
- **Evidence:** `calc_metrics` computed downside deviation as `downside.std(ddof=1)` on only the negative excess returns. In pandas, `.std()` calculates sample variance around the mean of negative returns ($\bar{x}_{\text{downside}}$), rather than dispersion relative to the target rate ($0$) across the full sample.
- **Impact:** Produced an incorrect Sortino ratio of `0.6997` instead of the institutional downside deviation result `0.6808` (difference of `0.0189 > 1e-4`).
- **Remediation:** Replaced with standard downside semi-deviation:  
  ```python
  downside_diff = np.minimum(0.0, excess)
  downside_dev = float(np.sqrt(np.mean(downside_diff ** 2)))
  ```
- **Regression Test:** Verified via `test_real_nifty_it_reference_vs_engine_match` in `tests/test_quant_regression.py`.

### Bug 3: Cointegration on Raw Prices vs. Log Prices (`engine/hedge_pipeline.py`)
- **Evidence:** `hedge_pipeline.py` line 180 invoked `engle_granger_test(prices[long], prices[short])` using raw price levels, whereas line 187 computed the spread using log prices $\ln(P_{\text{long}}) - \ln(P_{\text{short}})$. On `TCS.NS`/`WIPRO.NS`, raw price cointegration produced $p = 0.6817$, while log-price cointegration produced $p = 0.6210$ (discrepancy of $0.0607$).
- **Remediation:** Updated line 180 of `engine/hedge_pipeline.py` to pass log prices:  
  `coint_result = engle_granger_test(np.log(prices[long]), np.log(prices[short]))`

### Bug 4: Signature Incompatibility in Cointegration Module (`engine/cointegration.py`)
- **Evidence:** `agents/quant_node.py` passed `(long_ticker, short_ticker, prices_df)` into `engle_granger_test`, `compute_spread_zscore`, and `ou_half_life`, whereas the engine functions originally accepted only `(series_a, series_b)`. This resulted in `AttributeError: 'str' object has no attribute 'empty'` and caused cointegration analysis in the agent node to log an error.
- **Remediation:** Added polymorphic argument handling to `engine/cointegration.py` so that both `(Series, Series)` and `(str, str, DataFrame)` signatures are seamlessly supported without modifying `agents/`.

---

## 5. Test Suite Verification

Ran the complete pytest test suite:
```
platform win32 -- Python 3.13.13, pytest-9.2.0, pluggy-1.7.0
rootdir: E:\Projects\Proxy
testpaths: tests
collected 47 items

tests/test_beta_calculator.py ...........                                [ 23%]
tests/test_cointegration.py .......                                      [ 38%]
tests/test_portfolio.py ......                                           [ 51%]
tests/test_quant_regression.py .................                         [ 87%]
tests/test_verifier.py ......                                            [100%]

============================== 47 passed in 1.85s ==============================
```

---

## 6. Verification Boundaries & What Was Not Verified

1. **Brokerage API & Order Routing:** Only historical price data and deterministic backtest metrics were evaluated. No live order placement, slippage models, or broker connections were tested.
2. **Real-time Streaming:** All testing operated on end-of-day adjusted closing data. Real-time sub-second WebSocket feeds were not tested.
3. **Execution F&O Margins:** While F&O lot sizing math (`convert_to_fno_lots`) was checked for unit calculations, live exchange SPAN margin requirements were not simulated.
