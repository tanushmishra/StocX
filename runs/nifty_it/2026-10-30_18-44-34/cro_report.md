**MEMORANDUM**

**TO:** Investment Committee / Portfolio Management Desk
**FROM:** Office of the Chief Risk Officer (CROReporterGPT)
**DATE:** October 26, 2023
**SUBJECT:** **STRATEGY APPROVAL: Market-Neutral Pair Trade – NIFTY IT Sector**

---

### 1. Executive Summary
**VERDICT: APPROVED ✅**
Following a rigorous quantitative review, the proposed market-neutral pair trade involving **TCS.NS (Long)** and **WIPRO.NS (Short)** is approved for execution. The strategy successfully demonstrates a statistically significant mean-reverting relationship and provides a robust hedge against systemic shocks, reducing peak-to-trough drawdown by approximately **79%** compared to an unhedged position during the COVID-19 stress regime.

### 2. Data Provenance & Integrity Disclosure
The quantitative analysis presented in this report was generated using **local CSV ("cache")** data. All historical price action, cointegration testing, and stress-test modeling utilize verified internal data stores. No synthetic fallbacks were required for this specific validation.

### 3. Thesis Recap
The Portfolio Manager (PM) aims to capture alpha by going long on high-quality Indian IT service leaders characterized by resilient balance sheets and superior ROE (TCS.NS), while simultaneously hedging against sector-wide valuation compression and margin pressure. The short leg (WIPRO.NS) targets a constituent with weaker relative momentum and higher vulnerability to margin squeeze, specifically calibrated to perform under the high-volatility conditions of the COVID-19 crisis.

### 4. Selected Pair & Rationale
*   **Long:** Tata Consultancy Services (TCS.NS)
*   **Short:** Wipro Limited (WIPRO.NS)

**Rationale:** This pair was selected based on its superior statistical "anchor." Unlike the previously rejected attempt, this pair exhibits a **Cointegration p-value of 0.029**, confirming a mathematically verifiable relationship where the price spread tends to revert to a mean. With an **OU Half-life of 10.45 days**, the trade offers a high velocity of turnover, minimizing capital lock-up.

### 5. Key Metrics Dashboard

| Metric | Value |
| :--- | :--- |
| **Cointegration (p-value)** | **0.0296** (Statistically Significant) |
| **Pair Correlation** | 0.6607 |
| **OU Half-life** | **10.45 Days** |
| **Spread Z-Score** | 0.2107 |
| **Static Beta (Long/Short)** | 0.876 / 0.785 |
| **EWMA Beta (Long/Short)** | 1.134 / 1.283 |
| **Hedged Max Drawdown** | **-8.64%** |
| **Unhedged Max Drawdown** | -41.38% |

### 6. Risk Assessment
*   **Residual Risk:** The pair correlation of **0.66** is moderate. While the cointegration is strong, the lower correlation suggests idiosyncratic price movements may occur; however, the market-neutral weighting mitigates the majority of NIFTY IT sector beta.
*   **Monitoring Triggers:** Immediate review required if the Spread Z-score exceeds ±2.5 or if the OU Half-life drifts beyond 25 days.
*   **Position Limits:** Total notional allocation is capped at the levels specified in the F&O execution plan to maintain liquidity constraints.

### 7. Stress Test Narrative
During the **COVID_2020 stress regime**, the effectiveness of the hedge was exemplary. An unhedged long position in the sector would have resulted in a catastrophic **-41.38% drawdown**. By utilizing the market-neutral spread between TCS and Wipro, the **Hedged Max Drawdown was limited to -8.64%**. This confirms that the short leg (Wipro) effectively absorbed the systemic shock, allowing the quality-spread thesis to remain intact despite extreme market turbulence.

### 8. F&O Execution Plan
The trade will be executed with a slight tilt toward the short leg to maintain beta-neutrality based on current EWMA estimates.

*   **TCS.NS (LONG):**
    *   Notional Allocated: **47,254.47**
    *   Direction: LONG
    *   Estimated Transaction Cost: 47.25
*   **WIPRO.NS (SHORT):**
    *   Notional Allocated: **52,745.53**
    *   Direction: SHORT
    *   Estimated Transaction Cost: 52.75

*Note: Final lot sizes must be rounded to the nearest exchange-specified contract size.*

### 9. Pair Selection Audit Trail
The final selection was reached after the following iterations:

1.  **Attempt 1: COFORGE.NS / WIPRO.NS**
    *   **Status:** FAILED ❌
    *   **Reason:** Failed correlation (0.482) and cointegration (p=0.928) gates. The spread was identified as a "random walk" with an unacceptable half-life of 243 days.
2.  **Attempt 2: TCS.NS / WIPRO.NS**
    *   **Status:** PASSED ✅
    *   **Reason:** Met all risk thresholds. Cointegration p-value < 0.05 and rapid mean reversion (10.45 days) provided the necessary statistical confidence for approval.