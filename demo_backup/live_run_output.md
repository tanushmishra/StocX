# Live Dry Run Execution Report

*Executed on: 2026-10-31 11:22:38*

## Thesis 1 (IT): "Bullish on Indian IT, hedged against crash"

- **Execution Time:** 34.04 seconds
- **Macro Intent:** Sector = `NIFTY IT`, Benchmark = `^NSEI`, Lookback = `252` days, Stress Regime = `COVID_2020`
- **LLM Fallback Used:** `True` ("LLM unavailable: heuristic defaults used")
- **Screened Constituents:**
  - Long Candidates: COFORGE.NS, TCS.NS, PERSISTENT.NS, TECHM.NS
  - Short Candidates: WIPRO.NS, LTTS.NS, HCLTECH.NS, MPHASIS.NS, INFY.NS
- **Selected Pair:** Long `TCS.NS` vs Short `LTTS.NS`
- **Screening Attempts:** 5 / 5
- **Verification Verdict:** `REJECTED`

### Adversarial Risk Gate Verification
- **Correlation:** 0.43973451261316043 (Threshold >= 0.65)
- **Cointegration p-value:** N/A (Threshold < 0.05)
- **Hedged Beta:** N/A (Threshold |beta| < 0.15)
- **Unhedged MDD:** -0.241046
- **Hedged MDD:** -0.159118
- **Failed Checks:** [{'check': 'correlation', 'reason': 'Correlation 0.4397 < minimum threshold 0.65'}, {'check': 'cointegration', 'reason': 'Cointegration p-value 0.2601 >= threshold 0.05 (pair not cointegrated)'}, {'check': 'max_drawdown_reduction', 'reason': 'Hedged MDD (0.1591) is 66.0% of unhedged MDD (0.2410); must be < 50%'}]
- **Diagnostic:** 3 check(s) failed: correlation, cointegration, max_drawdown_reduction.

### Rejection Audit Log (5 attempts)
- Attempt 1: `COFORGE.NS / WIPRO.NS` -> 3 check(s) failed: correlation, cointegration, max_drawdown_reduction.
- Attempt 2: `COFORGE.NS / LTTS.NS` -> 3 check(s) failed: correlation, cointegration, max_drawdown_reduction.
- Attempt 3: `TCS.NS / WIPRO.NS` -> 1 check(s) failed: cointegration.
- Attempt 4: `COFORGE.NS / HCLTECH.NS` -> 3 check(s) failed: correlation, cointegration, max_drawdown_reduction.
- Attempt 5: `TCS.NS / LTTS.NS` -> 3 check(s) failed: correlation, cointegration, max_drawdown_reduction.

### Institutional CRO Report Summary

```text
# CRO Report (Fallback – LLM Unavailable)

**Status:** NOT APPROVED
**Data Source:** cache
**Thesis:** Bullish on Indian IT, hedged against crash
**Sector:** NIFTY IT
**Long:** TCS.NS
**Short:** LTTS.NS
**Attempts:** 5/5
**Rejections:** 5

_Full LLM-generated memo could not be produced.  See the message history for detailed node outputs._
...
```

---

## Thesis 2 (Banking): "Bullish on Indian banks, worried about rate hikes"

- **Execution Time:** 50.07 seconds
- **Macro Intent:** Sector = `NIFTY PSU BANK`, Benchmark = `^NSEI`, Lookback = `252` days, Stress Regime = `COVID_2020`
- **LLM Fallback Used:** `True` ("LLM unavailable: heuristic defaults used")
- **Screened Constituents:**
  - Long Candidates: MAHABANK.NS, BANKINDIA.NS, UNIONBANK.NS, BANKBARODA.NS, INDIANB.NS
  - Short Candidates: CANBK.NS, SBIN.NS, PNB.NS, CENTRALBK.NS, IOB.NS
- **Selected Pair:** Long `BANKINDIA.NS` vs Short `SBIN.NS`
- **Screening Attempts:** 5 / 5
- **Verification Verdict:** `REJECTED`

### Adversarial Risk Gate Verification
- **Correlation:** 0.5811971460306212 (Threshold >= 0.65)
- **Cointegration p-value:** N/A (Threshold < 0.05)
- **Hedged Beta:** N/A (Threshold |beta| < 0.15)
- **Unhedged MDD:** -0.263847
- **Hedged MDD:** -0.058713
- **Failed Checks:** [{'check': 'correlation', 'reason': 'Correlation 0.5812 < minimum threshold 0.65'}]
- **Diagnostic:** 1 check(s) failed: correlation.

### Rejection Audit Log (5 attempts)
- Attempt 1: `MAHABANK.NS / CANBK.NS` -> 3 check(s) failed: correlation, cointegration, max_drawdown_reduction.
- Attempt 2: `MAHABANK.NS / SBIN.NS` -> 3 check(s) failed: correlation, cointegration, max_drawdown_reduction.
- Attempt 3: `BANKINDIA.NS / CANBK.NS` -> 1 check(s) failed: cointegration.
- Attempt 4: `MAHABANK.NS / PNB.NS` -> 3 check(s) failed: correlation, cointegration, max_drawdown_reduction.
- Attempt 5: `BANKINDIA.NS / SBIN.NS` -> 1 check(s) failed: correlation.

### Institutional CRO Report Summary

```text
# CRO Report (Fallback – LLM Unavailable)

**Status:** NOT APPROVED
**Data Source:** yfinance
**Thesis:** Bullish on Indian banks, worried about rate hikes
**Sector:** NIFTY PSU BANK
**Long:** BANKINDIA.NS
**Short:** SBIN.NS
**Attempts:** 5/5
**Rejections:** 5

_Full LLM-generated memo could not be produced.  See the message history for detailed node outputs._
...
```

---


## Stage 7 Live Verification Run - 2026-10-31 11:56:23 UTC

### Thesis 1 (IT): "Bullish on Indian IT, hedged against crash"

- **Execution Time:** 41.51 seconds
- **Macro Intent:** Sector = `N/A`, Benchmark = `^NSEI`, Regime = `COVID_2020`
- **LLM Fallback Used:** `True`
- **Constituents Selected:** Long `N/A` vs Short `N/A`
- **Verification Verdict:** `N/A`
- **Individual Gate Results:**
  - Correlation: `N/A`
  - Cointegration p-value: `N/A`
  - Hedged MDD: `N/A` vs Unhedged MDD: `N/A`
  - Realized Hedged Beta: `N/A`
- **Failed Checks:** `[]`
- **Diagnostic:** N/A

### Thesis 2 (Banking): "Bullish on Indian banks, worried about rate hikes"

- **Execution Time:** 25.67 seconds
- **Macro Intent:** Sector = `N/A`, Benchmark = `^NSEI`, Regime = `COVID_2020`
- **LLM Fallback Used:** `True`
- **Constituents Selected:** Long `N/A` vs Short `N/A`
- **Verification Verdict:** `N/A`
- **Individual Gate Results:**
  - Correlation: `N/A`
  - Cointegration p-value: `N/A`
  - Hedged MDD: `N/A` vs Unhedged MDD: `N/A`
  - Realized Hedged Beta: `N/A`
- **Failed Checks:** `[]`
- **Diagnostic:** N/A



## Stage 7 Final Verification Dry Runs - 2026-10-31 11:58:44 UTC

### Thesis 1 (IT): "Bullish on Indian IT, hedged against crash"

- **Execution Time:** 37.82 seconds
- **Macro Intent:** Sector = `NIFTY IT`, Benchmark = `^NSEI`, Stress Regime = `COVID_2020`
- **LLM Fallback Used:** `True`
- **Constituents Evaluated:** Long `TCS.NS` vs Short `LTTS.NS`
- **Screening Attempts:** 5 / 5
- **Verification Verdict:** `REJECTED`
- **Adversarial Gate Measurements:**
  - Correlation: `0.43973451261316043`
  - Cointegration p-value: `N/A`
  - Hedged MDD: `-0.159118` vs Unhedged MDD: `-0.241046`
  - Realized Hedged Beta: `-0.0`
- **Failed Verification Criteria:** `[{'check': 'correlation', 'reason': 'Correlation 0.4397 < minimum threshold 0.65'}, {'check': 'cointegration', 'reason': 'Cointegration p-value 0.2601 >= threshold 0.05 (pair not cointegrated)'}, {'check': 'max_drawdown_reduction', 'reason': 'Hedged MDD (0.1591) is 66.0% of unhedged MDD (0.2410); must be < 50%'}]`
- **Verifier Diagnostic:** 3 check(s) failed: correlation, cointegration, max_drawdown_reduction.
- **Rejection Log History:**
  - Attempt 1: `N/A` -> 3 check(s) failed: correlation, cointegration, max_drawdown_reduction.
  - Attempt 2: `N/A` -> 3 check(s) failed: correlation, cointegration, max_drawdown_reduction.
  - Attempt 3: `N/A` -> 1 check(s) failed: cointegration.
  - Attempt 4: `N/A` -> 3 check(s) failed: correlation, cointegration, max_drawdown_reduction.
  - Attempt 5: `N/A` -> 3 check(s) failed: correlation, cointegration, max_drawdown_reduction.

```text
# CRO Report (Fallback – LLM Unavailable)

**Status:** NOT APPROVED
**Data Source:** cache
**Thesis:** Bullish on Indian IT, hedged against crash
**Sector:** NIFTY IT
**Long:** TCS.NS
**Short:** LTTS.NS
**Attempts:** 5/5
**Rejections:** 5

_Full LLM-generated memo could not be produced.  See the message history for detailed node outputs._
...
```

### Thesis 2 (Banking): "Bullish on Indian banks, worried about rate hikes"

- **Execution Time:** 35.08 seconds
- **Macro Intent:** Sector = `NIFTY PSU BANK`, Benchmark = `^NSEI`, Stress Regime = `COVID_2020`
- **LLM Fallback Used:** `True`
- **Constituents Evaluated:** Long `BANKINDIA.NS` vs Short `SBIN.NS`
- **Screening Attempts:** 5 / 5
- **Verification Verdict:** `REJECTED`
- **Adversarial Gate Measurements:**
  - Correlation: `0.5811971460306212`
  - Cointegration p-value: `N/A`
  - Hedged MDD: `-0.058713` vs Unhedged MDD: `-0.263847`
  - Realized Hedged Beta: `-0.0`
- **Failed Verification Criteria:** `[{'check': 'correlation', 'reason': 'Correlation 0.5812 < minimum threshold 0.65'}]`
- **Verifier Diagnostic:** 1 check(s) failed: correlation.
- **Rejection Log History:**
  - Attempt 1: `N/A` -> 3 check(s) failed: correlation, cointegration, max_drawdown_reduction.
  - Attempt 2: `N/A` -> 3 check(s) failed: correlation, cointegration, max_drawdown_reduction.
  - Attempt 3: `N/A` -> 1 check(s) failed: cointegration.
  - Attempt 4: `N/A` -> 3 check(s) failed: correlation, cointegration, max_drawdown_reduction.
  - Attempt 5: `N/A` -> 1 check(s) failed: correlation.

```text
# CRO Report (Fallback – LLM Unavailable)

**Status:** NOT APPROVED
**Data Source:** cache
**Thesis:** Bullish on Indian banks, worried about rate hikes
**Sector:** NIFTY PSU BANK
**Long:** BANKINDIA.NS
**Short:** SBIN.NS
**Attempts:** 5/5
**Rejections:** 5

_Full LLM-generated memo could not be produced.  See the message history for detailed node outputs._
...
```

