# StocX NIFTY IT Pipeline Execution Artifacts
**Run Timestamp:** `2026-10-30_18-44-34`  
**Pipeline Status:** `APPROVED ✅`  
**Data Provenance:** `cache` (Synthetic Fallback: **STRICTLY DISABLED**)  
**Execution Duration:** `52.24 seconds`  
**Gemini Models:** Fast=`gemini-3-flash-preview`, Reasoning=`gemini-3-flash-preview`  

---

## 1. What This Run Did
This run executed the full 6-stage autonomous agent pipeline for the **NIFTY IT** sector universe:
1. **Macro Intent Parser:** Mapped the PM thesis to sector `NIFTY IT`, benchmark `^NSEI`, lookback `252` days, and stress regime `COVID_2020`.
2. **Fundamental & Catalyst Screener:** Loaded real fundamentals from `data/fundamentals.csv`, computed composite fundamental scores for all sector constituents, fetched qualitative catalyst news, and selected candidate long/short pairs while respecting past rejection history.
3. **Quantitative Execution Engine:** Deterministically computed beta (OLS + EWMA), Pearson correlation, Engle-Granger cointegration, spread z-score, Ornstein-Uhlenbeck half-life, beta-neutral portfolio weights, backtested return series, and crisis drawdown under `COVID_2020`.
4. **Risk Verifier (Adversarial Gatekeeper):** Evaluated the pair against the 4 institutional risk gates:
   - Correlation $\ge 0.65$
   - Cointegration p-value $< 0.05$
   - Hedged beta $< 0.15$
   - Drawdown reduction ratio $< 0.50$
5. **Rejection & Self-Correction Loop:** Automatically re-routed rejected pairs back to the Screener with full memory of past rejections.
6. **CRO Reporter:** Generated an institutional memorandum via `gemini-3-flash-preview` summarizing key metrics, provenance, risk findings, and F&O contract execution.

---

## 2. Directory Contents & How to Inspect

| File | Description | How to Inspect |
| :--- | :--- | :--- |
| `state.json` | Complete serialized LangGraph state at the end of the pipeline run. | Open in any JSON viewer or parse with `json.load(open('state.json'))`. All keys match `HedgeBuilderState`. |
| `rejection_trace.json` | The complete chronological audit trail of all candidate pairs evaluated and rejected. | Check `rejections` array to see which pairs were tried, their failing metric, and rejection explanation. |
| `candidate_metrics.json` | Detailed deterministic quant calculations for the final candidate pair, including weights and screened universe. | Contains raw floats for betas, correlation, cointegration p-value, Sharpe, and drawdown stats. |
| `cro_report.md` | Institutional executive memorandum ready for the Investment Committee or CRO. | Render with any Markdown viewer or Streamlit's `st.markdown()`. |
| `execution_log.txt` | Complete stdout/stderr execution log with timestamped agent actions and secret redactions. | Plain text inspection of pipeline telemetry. |
| `lookback_comparison.json` | Complete quantitative gate evaluation of all NIFTY IT candidate pairs comparing 252-day vs 504-day lookbacks. | Parse with `json.load(open('lookback_comparison.json'))`. |

---

## 3. Lookback Comparison Analysis (252-Day vs 504-Day)

Institutional comparison of candidate pairs across lookback horizons:

| Candidate Pair | 252d Correlation | 252d Cointegration $p$ | 252d Verdict | 504d Correlation | 504d Cointegration $p$ | 504d Verdict |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **COFORGE.NS / INFY.NS** | 0.61 | 0.708 | REJECTED ❌ | 0.60 | 0.944 | REJECTED ❌ |
| **COFORGE.NS / MPHASIS.NS** | 0.68 | 0.326 | REJECTED ❌ | 0.68 | 0.873 | REJECTED ❌ |
| **COFORGE.NS / HCLTECH.NS** | 0.57 | 0.959 | REJECTED ❌ | 0.57 | 0.912 | REJECTED ❌ |
| **COFORGE.NS / LTTS.NS** | 0.39 | 0.831 | REJECTED ❌ | 0.38 | 0.743 | REJECTED ❌ |
| **COFORGE.NS / WIPRO.NS** | 0.46 | 0.819 | REJECTED ❌ | 0.48 | 0.929 | REJECTED ❌ |
| **TCS.NS / INFY.NS** | 0.78 | 0.441 | REJECTED ❌ | 0.77 | 0.083 | REJECTED ❌ |
| **TCS.NS / WIPRO.NS** | 0.68 | 0.491 | REJECTED ❌ | **0.66** | **0.030** | **APPROVED ✅** |
| **INFY.NS / WIPRO.NS** | 0.60 | 0.122 | REJECTED ❌ | 0.63 | 0.017 | REJECTED ❌ (Corr < 0.65) |
| **TECHM.NS / WIPRO.NS** | 0.54 | 0.619 | REJECTED ❌ | 0.54 | 0.528 | REJECTED ❌ |
| **PERSISTENT.NS / LTTS.NS** | 0.41 | 0.382 | REJECTED ❌ | 0.39 | 0.275 | REJECTED ❌ |
| **PERSISTENT.NS / COFORGE.NS** | 0.68 | 0.177 | REJECTED ❌ | 0.71 | 0.463 | REJECTED ❌ |
| **HCLTECH.NS / TECHM.NS** | 0.70 | 0.505 | REJECTED ❌ | 0.68 | 0.854 | REJECTED ❌ |

- **Key Takeaway:** Over 252 days, spread non-stationarity rejected 100% of candidate pairs. Expanding to a 504-day structural horizon reveals genuine long-run cointegration for **TCS.NS / WIPRO.NS** ($p = 0.030 < 0.05$, $r = 0.66 \ge 0.65$), passing all 4 gates.

---

## 4. UI Dashboard Integration Guide (For Dhairya)

Dhairya, here are the exact state fields to bind in the Streamlit dashboard:

### Top-Level Header & Badges
- **Status Pill:** Bind to `state["approved"]` -> `True` displays **APPROVED**, `False` displays **REJECTED**.
- **Data Source Pill:** Bind to `state["data_source"]` ->
  - `"cache"`: Render green badge `[Data: Local Cache (Validated)]`
  - `"yfinance"`: Render blue badge `[Data: Live Market Data (yfinance)]`
  - `"synthetic_fallback"`: Render red warning badge `[⚠️ Synthetic Simulation]`
- **Selected Pair:** Bind to `state["selected_long"]` and `state["selected_short"]`.

### Risk & Quantitative Metrics Table
Bind to `state["pair_metrics"]` and `state["hedged_stats"]`:
- **Static Beta (Long / Short):** `pair_metrics["static_beta_long"]` / `pair_metrics["static_beta_short"]`
- **EWMA Beta (Long / Short):** `pair_metrics["ewma_beta_long"]` / `pair_metrics["ewma_beta_short"]`
- **Pair Correlation:** `pair_metrics["pair_correlation"]` (Gate: $\ge 0.65$)
- **Cointegration p-value:** `pair_metrics["cointegration"]["p_value"]` (Gate: $< 0.05$)
- **Spread Z-Score:** `pair_metrics["spread_zscore"]`
- **OU Half-Life:** `pair_metrics["ou_half_life"]` days
- **Hedged vs. Unhedged Sharpe:** `hedged_stats["sharpe"]` vs. `unhedged_stats["sharpe"]`
- **Hedged vs. Unhedged Max Drawdown:** `hedged_stats["max_drawdown"]` vs. `unhedged_stats["max_drawdown"]`

### Portfolio Weights & F&O Execution
- **Weights:** Bind to `state["weights"]["long_weight"]` and `state["weights"]["short_weight"]`.
- **F&O Execution Plan:** Bind to `state["fno_execution"]` (contains `long_lot_size`, `short_lot_size`, `margin_estimate`, etc.).

### Executive Memo
- **CRO Report:** Bind to `state["cro_report"]` and render via `st.markdown(state["cro_report"])`.

### Self-Correction & Rejection Audit
- **Rejection Log:** Bind to `state["rejection_log"]` (list of `('long', 'short', 'reason')`) to render the interactive rejection timeline.
