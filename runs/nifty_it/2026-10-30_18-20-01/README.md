# StocX NIFTY IT Pipeline Execution Artifacts
**Run Timestamp:** `2026-10-30_18-20-01`  
**Pipeline Status:** `NOT APPROVED ❌`  
**Data Provenance:** `yfinance` (Synthetic Fallback: **STRICTLY DISABLED**)  
**Execution Duration:** `36.73 seconds`

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
6. **CRO Reporter:** Generated an executive institutional memorandum via Gemini 2.5 Pro summarizing key metrics, provenance, risk findings, and F&O contract execution.

---

## 2. Directory Contents & How to Inspect

| File | Description | How to Inspect |
| :--- | :--- | :--- |
| `state.json` | Complete serialized LangGraph state at the end of the pipeline run. | Open in any JSON viewer or parse with `json.load(open('state.json'))`. All keys match `HedgeBuilderState`. |
| `rejection_trace.json` | The complete chronological audit trail of all candidate pairs evaluated and rejected. | Check `rejections` array to see which pairs were tried, their failing metric, and rejection explanation. |
| `candidate_metrics.json` | Detailed deterministic quant calculations for the final candidate pair, including weights and screened universe. | Contains raw floats for betas, correlation, cointegration p-value, Sharpe, and drawdown stats. |
| `cro_report.md` | Institutional executive memorandum ready for the Investment Committee or CRO. | Render with any Markdown viewer or Streamlit's `st.markdown()`. |
| `execution_log.txt` | Complete stdout/stderr execution log with timestamped agent actions and secret redactions. | Plain text inspection of pipeline telemetry. |

---

## 3. UI Dashboard Integration Guide (For Dhairya)

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
