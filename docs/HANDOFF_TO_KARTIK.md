# Handoff to Kartik (LangGraph Agent Lead)

**From:** Tanush (Quant Engine Lead)  
**To:** Kartik (Agent Architecture & Pipeline Lead)  
**Date:** 2026-10-30  
**Repository Branch:** `proA/quant-checks`

---

## 1. Final Guardrail Thresholds in Use

The deterministic quantitative engine enforces the four hardcoded guardrail thresholds in `engine/verifier.py`:

```python
_MIN_CORRELATION: float = 0.65          # Gate 1: Pearson return correlation >= 0.65
_MAX_COINT_PVALUE: float = 0.05         # Gate 2: Engle-Granger log-price ADF p-value < 0.05
_MDD_RATIO_THRESHOLD: float = 0.50      # Gate 3: Hedged MDD / Unhedged MDD < 0.50 (at least 50% DD reduction)
_MAX_REALIZED_BETA: float = 0.15        # Gate 4: |Realized market beta| < 0.15
```

---

## 2. Sector Approval Status & Top Candidate Pairs

### Sector Approval Summary
* **Under Strict Default Gates:** **All 4 sectors (`NIFTY_IT`, `NIFTY_BANK`, `NIFTY_AUTO`, `NIFTY_PHARMA`) had NO pairs pass all 4 gates simultaneously across both test windows.**
* **Why:** Cointegration significance ($p < 0.05$) is statistically difficult to achieve on 140–160 day estimation windows, and pharma correlations rarely exceed $0.65$.

### Top Candidate Pairs on TEST Windows (`covid_2020` & `election_2024`)

The following pairs represent the strongest institutional candidates evaluated on the test windows from `analysis/results/sweep_results.csv`, passing 3 of 4 gates and delivering substantial crisis drawdown protection:

#### 1. NIFTY_IT
* **Candidate 1: `WIPRO.NS` (Long) / `TCS.NS` (Short) [Election 2024]**
  - Correlation: `0.5643` | Coint $p$: `0.0399` (**PASS**) | MDD Ratio: `0.1852` (**PASS** - 81.5% DD reduction)
  - Realized Beta: `0.1025` (**PASS**) | Annualized Sharpe: `3.1331` | Half-Life: `13.56` days
* **Candidate 2: `INFY.NS` (Long) / `TCS.NS` (Short) [Election 2024]**
  - Correlation: `0.7245` (**PASS**) | Coint $p$: `0.9518` | MDD Ratio: `0.3119` (**PASS** - 68.8% DD reduction)
  - Realized Beta: `0.0758` (**PASS**) | Annualized Sharpe: `4.3497` | Half-Life: `17.48` days
* **Candidate 3: `MPHASIS.NS` (Long) / `TECHM.NS` (Short) [COVID 2020]**
  - Correlation: `0.0608` | Coint $p$: `0.0377` (**PASS**) | MDD Ratio: `0.2517` (**PASS** - 74.8% DD reduction)
  - Realized Beta: `0.0534` (**PASS**) | Annualized Sharpe: `-0.0122` | Half-Life: `12.19` days

#### 2. NIFTY_BANK
* **Candidate 1: `BANKBARODA.NS` (Long) / `SBIN.NS` (Short) [Election 2024]**
  - Correlation: `0.7091` (**PASS**) | Coint $p$: `0.6239` | MDD Ratio: `0.0825` (**PASS** - 91.8% DD reduction)
  - Realized Beta: `0.0598` (**PASS**) | Annualized Sharpe: `-0.3554` | Half-Life: `22.56` days
* **Candidate 2: `HDFCBANK.NS` (Long) / `KOTAKBANK.NS` (Short) [COVID 2020]**
  - Correlation: `0.6616` (**PASS**) | Coint $p$: `0.4145` | MDD Ratio: `0.2026` (**PASS** - 79.7% DD reduction)
  - Realized Beta: `-0.0645` (**PASS**) | Annualized Sharpe: `0.0508` | Half-Life: `12.57` days
* **Candidate 3: `IDFCFIRSTB.NS` (Long) / `AUBANK.NS` (Short) [COVID 2020]**
  - Correlation: `0.1756` | Coint $p$: `0.0247` (**PASS**) | MDD Ratio: `0.1687` (**PASS** - 83.1% DD reduction)
  - Realized Beta: `-0.0864` (**PASS**) | Annualized Sharpe: `2.1550` | Half-Life: `14.59` days

#### 3. NIFTY_AUTO
* **Candidate 1: `EICHERMOT.NS` (Long) / `TVSMOTOR.NS` (Short) [COVID 2020]**
  - Correlation: `0.6319` | Coint $p$: `0.0162` (**PASS**) | MDD Ratio: `0.1815` (**PASS** - 81.9% DD reduction)
  - Realized Beta: `0.0711` (**PASS**) | Annualized Sharpe: `0.0110` | Half-Life: `13.15` days
* **Candidate 2: `HEROMOTOCO.NS` (Long) / `BAJAJ-AUTO.NS` (Short) [COVID 2020]**
  - Correlation: `0.6898` (**PASS**) | Coint $p$: `0.1151` | MDD Ratio: `0.2389` (**PASS** - 76.1% DD reduction)
  - Realized Beta: `-0.1178` (**PASS**) | Annualized Sharpe: `1.3207` | Half-Life: `30.40` days
* **Candidate 3: `MARUTI.NS` (Long) / `BAJAJ-AUTO.NS` (Short) [COVID 2020]**
  - Correlation: `0.6333` | Coint $p$: `0.0393` (**PASS**) | MDD Ratio: `0.3439` (**PASS** - 65.6% DD reduction)
  - Realized Beta: `-0.0902` (**PASS**) | Annualized Sharpe: `0.0028` | Half-Life: `16.27` days

#### 4. NIFTY_PHARMA
* **Candidate 1: `DRREDDY.NS` (Long) / `SUNPHARMA.NS` (Short) [Election 2024]**
  - Correlation: `0.3799` | Coint $p$: `0.0047` (**PASS**) | MDD Ratio: `0.4461` (**PASS** - 55.4% DD reduction)
  - Realized Beta: `-0.0057` (**PASS**) | Annualized Sharpe: `3.4811` | Half-Life: `8.26` days
* **Candidate 2: `DRREDDY.NS` (Long) / `DIVISLAB.NS` (Short) [COVID 2020]**
  - Correlation: `0.2701` | Coint $p$: `0.0013` (**PASS**) | MDD Ratio: `0.4836` (**PASS** - 51.6% DD reduction)
  - Realized Beta: `0.0816` (**PASS**) | Annualized Sharpe: `0.8887` | Half-Life: `8.82` days
* **Candidate 3: `TORNTPHARM.NS` (Long) / `DIVISLAB.NS` (Short) [COVID 2020]**
  - Correlation: `0.2094` | Coint $p$: `0.0431` (**PASS**) | MDD Ratio: `0.4917` (**PASS** - 50.8% DD reduction)
  - Realized Beta: `0.0705` (**PASS**) | Annualized Sharpe: `1.0089` | Half-Life: `11.02` days

---

## 3. Real Saved Rejection Example

* **File Location:** `analysis/results/rejection_example.json`
* **Pair:** `HDFCBANK.NS` (Long) vs. `KOTAKBANK.NS` (Short)
* **Regime Window:** `covid_2020` (Estimation: `2019-06-01` to `2020-01-31`, Test: `2020-02-01` to `2020-04-30`)
* **Failed Gate:** `cointegration`
* **Measured Value:** `p = 0.4145`
* **Required Threshold:** `p < 0.05`
* **Quantitative Context:** HDFC Bank and Kotak Bank had strong return correlation (`0.6616`), excellent drawdown reduction (Hedged MDD was `7.81%` vs. unhedged MDD of `38.53%`, ratio `0.2026`), and market-neutral realized beta (`-0.0645`). However, the Engle-Granger ADF test failed to reject non-stationarity ($p = 0.4145$), triggering a deterministic rejection by the verifier.

---

## 4. Three Key Directives for Kartik's Agent Implementation

1. **Implement Stateful Rejection Looping in LangGraph:**
   - When `verifier.py` rejects a pair, the Adversarial Risk Verifier node must not crash or terminate the run. It must inspect `state["failed_checks"]` and loop back to the Screener Agent node with the rejection feedback.
   - The Screener Agent should exclude the failed pair and select the next highest-scoring candidate pair, or report an honest rejection if all candidates fail.

2. **Signature Compatibility in Node Execution:**
   - In `agents/quant_node.py`, the calls to `engle_granger_test`, `compute_spread_zscore`, and `ou_half_life` previously passed `(long_ticker, short_ticker, prices)`.
   - The quant engine in `engine/cointegration.py` has now been updated to natively accept both `(Series, Series)` and `(str, str, DataFrame)`. You can call either convention cleanly without runtime errors.

3. **Incorporate Rejection Explanations in the CRO Report:**
   - As demonstrated by the empirical sweep, cointegration failure ($p \ge 0.05$) and correlation thresholds ($\rho < 0.65$) are the primary reasons pairs fail in real market data.
   - When the agent presents a rejected trade, ensure the LLM explains the exact quantitative reason: for example, *"While HDFC/Kotak reduced drawdown by 80%, the spread exhibited non-stationary drift pre-crisis ($p=0.4145$), violating statistical cointegration guardrails."*
