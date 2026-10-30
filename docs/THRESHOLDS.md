# Quantitative Guardrail Thresholds Analysis

**Author:** Tanush (Quant Engine Lead)  
**Date:** 2026-10-30  
**Repository Branch:** `proA/quant-checks`

---

## 1. Current Guardrail Thresholds in Use

The Adversarial Risk Verifier (`engine/verifier.py` and `config.py`) enforces four deterministic mathematical guardrails before approving any pair for hedged execution:

| Gate | Metric Name | Threshold Rule | Financial & Quantitative Rationale |
| :---: | :--- | :---: | :--- |
| **1** | **Pair Return Correlation** | $\rho \ge 0.65$ | Ensures both assets belong to the same factor ecosystem so macro tides cancel out. |
| **2** | **Cointegration ($p$-value)** | $p < 0.05$ | Engle-Granger ADF test on log prices confirming spread mean reversion and preventing indefinite drift. |
| **3** | **Drawdown Reduction Ratio** | $\frac{\text{MDD}_{\text{hedged}}}{\text{MDD}_{\text{unhedged}}} < 0.50$ | Hedged portfolio must reduce crisis peak-to-trough decline by at least $50\%$. |
| **4** | **Realized Market Beta** | $\vert\beta_{\text{realized}}\vert < 0.15$ | Hedged strategy must maintain near-zero market sensitivity throughout the crisis event. |

*Default status:* All four thresholds remain strictly active and unmodified in `config.py`.

---

## 2. Empirical Pass Rates Across Train & Test Windows

A total of **1,356 pair-regime combinations** were evaluated out-of-sample across all four NSE sectors.

### Out-of-Sample Regime Splits:
* **TRAIN Windows (Pre-event estimation $\rightarrow$ Crisis evaluation):**
  - `gfc_2008`: Estimate `2007-06-01` to `2007-12-31` (146 bars) $\rightarrow$ Test `2008-01-01` to `2008-12-31` (247 bars)
  - `tech_2022`: Estimate `2021-06-01` to `2021-12-31` (148 bars) $\rightarrow$ Test `2022-01-01` to `2022-06-30` (123 bars)
* **TEST Windows (Out-of-sample stress verification):**
  - `covid_2020`: Estimate `2019-06-01` to `2020-01-31` (166 bars) $\rightarrow$ Test `2020-02-01` to `2020-04-30` (58 bars)
  - `election_2024`: Estimate `2023-10-01` to `2024-05-15` (152 bars) $\rightarrow$ Test `2024-05-16` to `2024-06-30` (32 bars)

### Full Empirical Pass Rate Matrix

| Sector | Split | Total Pairs | Correlation Gate ($\ge 0.65$) | Cointegration Gate ($p < 0.05$) | MDD Ratio Gate ($< 0.50$) | Realized Beta Gate ($< 0.15$) | ALL 4 GATES PASSED |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **NIFTY_IT** | **TRAIN** | 114 | 5.3% | 7.0% | 93.9% | 66.7% | **0.0%** |
| **NIFTY_IT** | **TEST** | 144 | 4.2% | 7.6% | 66.0% | 61.1% | **0.0%** |
| **NIFTY_BANK** | **TRAIN** | 204 | 5.9% | 4.4% | 67.2% | 65.7% | **0.0%** |
| **NIFTY_BANK** | **TEST** | 264 | 4.5% | 4.9% | 62.1% | 49.2% | **0.0%** |
| **NIFTY_AUTO** | **TRAIN** | 144 | 1.4% | 6.9% | 45.1% | 48.6% | **0.0%** |
| **NIFTY_AUTO** | **TEST** | 144 | 2.8% | 3.5% | 62.5% | 47.2% | **0.0%** |
| **NIFTY_PHARMA** | **TRAIN** | 162 | 0.0% | 9.9% | 27.8% | 49.4% | **0.0%** |
| **NIFTY_PHARMA** | **TEST** | 180 | 0.0% | 11.1% | 23.9% | 75.6% | **0.0%** |

---

## 3. Quantitative Diagnosis: Why Did Zero Pairs Pass All 4 Gates?

When analyzing why zero pairs passed all four gates simultaneously, two structural quantitative bottlenecks emerge from the data:

### Bottleneck A: Statistical Sample Size & Cointegration Power
- **The Issue:** The estimation windows range from 146 to 166 trading days (approx. 7 calendar months).
- **The Math:** In the Engle-Granger two-step procedure, the Augmented Dickey-Fuller (ADF) test must reject the null hypothesis of a unit root at $p < 0.05$ (t-stat $< -3.34$). In small samples ($T \approx 140$ bars), an AR(1) process with a realistic half-life of 45 to 90 trading days only completes 1 to 2 cycles of mean reversion.
- **The Consequence:** The statistical test suffers high Type II error rates (failing to reject the unit root null hypothesis even when economic cointegration is present), resulting in a low pass rate of $4.4\%$ to $11.1\%$ across all sectors.

### Bottleneck B: Idiosyncratic Divergence & Sector Correlation
- **The Issue:** The 0.65 correlation threshold is reasonable for large-cap IT and PSU banking duopolies, but fails in sectors with company-specific risk profiles.
- **The Math:** In `NIFTY_PHARMA`, pairwise correlations in the training windows had a mean of $0.2666$, a median of $0.2659$, and a maximum of $0.6200$. Zero pharma pairs reached $0.65$.
- **The Reason:** Pharmaceutical companies in India (e.g., Sun Pharma, Cipla, Dr. Reddy's, Divi's, Lupin) face independent drug pipeline approvals, US FDA form 483 inspection observations, and divergent geographic revenue splits that decouple daily returns despite shared sector classification.

---

## 4. Honest Quant Recommendations (For Team Discussion)

Per the golden rules, **no thresholds were tuned on test windows and no config values were modified**. The following recommendations are presented for discussion:

### Recommendation 1: Calibrate Correlation Threshold by Sector
* **Observation:** In the training set, lowering correlation to $\ge 0.50$ allowed 4 to 10 pairs to pass multiple gates while preserving strong hedging efficacy (MDD reduction still exceeded 70%).
* **Proposed Adjustment:**
  - `NIFTY_BANK` & `NIFTY_IT`: Keep $\rho \ge 0.55$
  - `NIFTY_AUTO` & `NIFTY_PHARMA`: Calibrate to $\rho \ge 0.40$

### Recommendation 2: Dual Stationarity Gate (Cointegration OR OU Half-Life)
* **Observation:** In short lookback windows ($T < 200$), Engle-Granger is overly conservative. However, Ornstein-Uhlenbeck half-life estimation directly measures mean-reversion speed without requiring severe asymptotic critical values.
* **Proposed Adjustment:** Accept pairs where *either* `coint_p < 0.10` *or* `5 <= ou_half_life <= 60 days`.

---

## 5. Plain-Language Limitations

1. **Finite Crisis Regimes:** The engine evaluates four historical stress episodes. Future crises may exhibit liquidity dynamics, volatility spikes, or correlation breakdowns unlike historical precedents.
2. **Static In-Window Beta Assumption:** Betas are estimated on trailing data. During abrupt market dislocations, individual stock sensitivities can diverge rapidly from their historical estimates (beta drift).
3. **Absence of Fundamental Inputs in Weight Sizing:** Beta-neutral weights ($w_L, w_S$) are derived strictly from covariance math. Fundamental scores (ROE, PE, revenue growth) screen candidates but do not alter position sizing.
4. **Regime Dependency of Cointegration:** Cointegration is not an immutable law of physics; structural shifts (regulatory changes, management transitions, corporate actions) can permanently break historical price parity.
