# Verified Quantitative Figures & Audit Trail

**Repository Branch:** `feat/platform-lite`  
**Standard:** Zero Numerical Hallucination | Deterministic Math Engine Only  
**Audit Rule:** Every number in this document originates directly from a verified repository artifact or execution log. No simulated or invented values.

---

## 1. Out-of-Sample COVID-19 Crash Test (TCS Long / WIPRO Short)

* **Source Artifact:** [`docs/QUANT_CHECK_REPORT.md`](file:///e:/Projects/Proxy/docs/QUANT_CHECK_REPORT.md#L68-L93)
* **Estimation Window:** `2019-06-01` to `2020-01-31` (Pre-crash baseline, 166 trading days)
* **Crash Evaluation Window:** `2020-02-01` to `2020-04-30` (COVID peak sell-off, 58 trading days)
* **Pre-Crash Sizing Betas:**
  - $\beta_{\text{TCS}} = 0.781123$ ([`docs/QUANT_CHECK_REPORT.md:74`](file:///e:/Projects/Proxy/docs/QUANT_CHECK_REPORT.md#L74))
  - $\beta_{\text{WIPRO}} = 0.965070$ ([`docs/QUANT_CHECK_REPORT.md:75`](file:///e:/Projects/Proxy/docs/QUANT_CHECK_REPORT.md#L75))
  - Capital Weights: $w_{\text{TCS}} = +0.552671$, $w_{\text{WIPRO}} = -0.447329$ ([`docs/QUANT_CHECK_REPORT.md:77-78`](file:///e:/Projects/Proxy/docs/QUANT_CHECK_REPORT.md#L77-L78))

### Crash Verification Metric Results:
| Metric | Value | Threshold Gate | Gate Verdict | Reference Source |
| :--- | :---: | :---: | :---: | :--- |
| **Unhedged Max Drawdown** | `25.61%` (`0.256096`) | — | — | [`docs/QUANT_CHECK_REPORT.md:87`](file:///e:/Projects/Proxy/docs/QUANT_CHECK_REPORT.md#L87) |
| **Hedged Max Drawdown** | `11.51%` (`0.115100`) | — | — | [`docs/QUANT_CHECK_REPORT.md:86`](file:///e:/Projects/Proxy/docs/QUANT_CHECK_REPORT.md#L86) |
| **Drawdown Reduction Ratio** | `0.4494` (`0.449440`) | $< 0.50$ | **PASS** | [`docs/QUANT_CHECK_REPORT.md:88`](file:///e:/Projects/Proxy/docs/QUANT_CHECK_REPORT.md#L88) |
| **Realized Hedged Beta** | `0.4214` (`0.421417`) | $|\beta| < 0.15$ | **FAIL** | [`docs/QUANT_CHECK_REPORT.md:89`](file:///e:/Projects/Proxy/docs/QUANT_CHECK_REPORT.md#L89) |
| **Pair Return Correlation** | `0.6200` (`0.619978`) | $\ge 0.65$ | **FAIL** | [`docs/QUANT_CHECK_REPORT.md:76`](file:///e:/Projects/Proxy/docs/QUANT_CHECK_REPORT.md#L76) |
| **Cointegration p-value** | `0.6210` (`0.620957`) | $< 0.05$ | **FAIL** | [`docs/QUANT_CHECK_REPORT.md:84`](file:///e:/Projects/Proxy/docs/QUANT_CHECK_REPORT.md#L84) |

> [!IMPORTANT]
> **Adversarial Outcome:** This is a crash test, NOT an approved hedge. Although downside peak-to-trough decline was compressed from 25.61% to 11.51%, the pair failed three out of four adversarial gates (Beta Neutrality, Correlation, and Cointegration) and was rejected by the deterministic verifier.

---

## 2. Full Historical Sweep Matrix (1,356 Pair-Regime Tests)

* **Source Artifact:** [`analysis/results/sweep_results.csv`](file:///e:/Projects/Proxy/analysis/results/sweep_results.csv)
* **Total Executed Tests:** **`1,356`** pair-regime combinations across Indian equities.
* **Sectors Covered (4):** `NIFTY_IT`, `NIFTY_BANK`, `NIFTY_AUTO`, `NIFTY_PHARMA` (Data exists for 6 sectors, but sweep formally covers these 4 sectors).
* **Stress Regimes Covered (4):**
  1. `gfc_2008` (Global Financial Crisis)
  2. `covid_2020` (Pandemic Market Crash)
  3. `tech_2022` (Tech Valuation Sell-Off)
  4. `election_2024` (Lok Sabha Election Volatility)
* **Overall Passing Pairs:** **`0`** pairs passed all four verification gates simultaneously under baseline thresholds.

### Verification Criteria Enforced:
1. Return Correlation $\ge 0.65$
2. Engle-Granger Cointegration $p$-value $< 0.05$
3. Max Drawdown Reduction Ratio $< 0.50$ (Hedged MDD $< 50\%$ of unhedged)
4. Absolute Realized Beta $|\beta_{\text{realized}}| < 0.15$

---

## 3. Official Rejection Showcase Pair (`HDFCBANK.NS` / `KOTAKBANK.NS`)

* **Source Artifact:** [`analysis/results/rejection_example.json`](file:///e:/Projects/Proxy/analysis/results/rejection_example.json) and [`docs/SHOWCASE_PAIRS.md:70-87`](file:///e:/Projects/Proxy/docs/SHOWCASE_PAIRS.md#L70-L87)
* **Pair:** Long `HDFCBANK.NS` ($w = +0.5054$) / Short `KOTAKBANK.NS` ($w = -0.4946$)
* **Stress Window:** `covid_2020`

### Measured Gate Outcomes:
1. **Gate 1 (Correlation):** **`0.6616`** $\ge 0.65$ $\rightarrow$ **PASS**
2. **Gate 2 (Cointegration):** **`p = 0.4145`** $\ge 0.05$ $\rightarrow$ **FAIL (REJECTED)**
3. **Gate 3 (Drawdown Reduction):** Unhedged MDD `38.53%`, Hedged MDD `7.81%`, Ratio $= 0.2026 < 0.50$ $\rightarrow$ **PASS (79.74% Drawdown Cut)**
4. **Gate 4 (Realized Beta):** **`-0.0645`** ($|-0.0645| < 0.15$) $\rightarrow$ **PASS**

### Institutional Lesson:
Even with exceptional drawdown suppression (38.5% down to 7.8%), the pair spread lacked mathematical stationarity over the 7-month estimation window ($p = 0.4145$). The verifier strictly rejected the pair, proving the adversarial architecture eliminates false-positive hedges.

---

## 4. Post-Hoc Exploratory Lookback Study (2-Year Window)

* **Source Artifact:** [`docs/SHOWCASE_PAIRS.md:90-121`](file:///e:/Projects/Proxy/docs/SHOWCASE_PAIRS.md#L90-L121)
* **Status:** Exploratory investigation conducted after seeing the initial failure to study sample-size sensitivity of the Engle-Granger ADF test.
* **Findings:**
  - When the pre-event lookback window for `HDFCBANK.NS` / `KOTAKBANK.NS` was extended from $\sim 7$ months (166 daily bars) to 2 years (489 daily bars), the cointegration $p$-value dropped from **`0.4145`** to **`0.0333`** (crossing into the passing region $p < 0.05$).
  - **Rule Compliance:** Thresholds in `config.py` were NOT modified. The 2Y lookback is available in the dashboard dropdown as an exploratory setting and labeled accordingly.

---

## 5. Verified Deterministic Quantitative Metrics Count

* **Source Artifact:** [`docs/QUANT_CHECK_REPORT.md:70-93`](file:///e:/Projects/Proxy/docs/QUANT_CHECK_REPORT.md#L70-L93)
* **Total Distinct Math Metrics:** **`17`**
  1. Static OLS Beta Long
  2. Static OLS Beta Short
  3. Pair Return Pearson Correlation
  4. Beta-Neutral Weight Long ($w_L$)
  5. Beta-Neutral Weight Short ($w_S$)
  6. Ornstein-Uhlenbeck Mean-Reversion Half-Life
  7. RiskMetrics EWMA Beta Long ($\lambda=0.94$)
  8. RiskMetrics EWMA Beta Short ($\lambda=0.94$)
  9. Rolling Window Beta Long (60-day)
  10. Rolling Window Beta Short (60-day)
  11. Engle-Granger Two-Step Cointegration ADF $p$-value
  12. Peak-to-Trough Maximum Drawdown (Hedged)
  13. Peak-to-Trough Maximum Drawdown (Unhedged)
  14. Drawdown Reduction Ratio ($\text{MDD}_H / \text{MDD}_U$)
  15. Realized Out-of-Sample Portfolio Beta
  16. Annualized Sharpe Ratio (Simple daily $R_f / 252$)
  17. Sortino Ratio & Parametric Value-at-Risk (95% VaR)
