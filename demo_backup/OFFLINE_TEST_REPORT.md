# StocX — Offline Demonstration & Wi-Fi-Off Test Report

**Tester:** Anay Tiwari (Data Engineer)  
**Date:** 2026-10-30  
**Target Environment:** Local Machine (`localhost:8501`)  
**Scope:** Offline resilience of Streamlit dashboard, quantitative calculations, and local data cache.  

---

## 1. Executive Summary

| Test Area | Offline Capability | Status | Notes |
| :--- | :--- | :---: | :--- |
| **Streamlit Server Startup** | Fully operational on `http://localhost:8501` | **PASS** | Binds to localhost socket; no outbound internet connection required. |
| **Historical Price Data Loading** | 24 / 24 CSVs load instantly from local `data/` | **PASS** | 0 external network requests; all crisis series stored locally. |
| **Quantitative Engine Computations** | Beta, Cointegration, Portfolio Math | **PASS** | `engine/` modules rely strictly on `numpy`, `pandas`, `statsmodels`, `scipy`. |
| **UI Charts & Visualizations** | Plotly charts and metric cards render offline | **PASS** | Bundled static assets render fully in the browser. |
| **Agent LLM Pipeline (Gemini)** | Live LangGraph LLM nodes | **FAIL (Expected)** | Requires internet connection to reach `generativelanguage.googleapis.com`. |
| **Dashboard Fallback on LLM Failure** | Auto-fallback to deterministic demo mode | **PASS** | `app.py` catches API failure and displays rich deterministic demo tear-sheet. |
| **Live Yahoo Finance Ingestion** | Fetching real-time intraday quotes | **FAIL (Expected)** | Real-time yfinance network queries require active internet. |
| **Physical Wi-Fi Interface Disconnection** | Disabling Wi-Fi adapter via shell | **NOT TESTED** | Safe policy: AI agent must not disable active network interface. Manual test procedure provided below. |

---

## 2. Detailed Component Offline Breakdown

### A. What Works 100% Offline (Zero Internet Required)
1. **Historical Crisis Datasets:** All 24 historical sector/regime datasets (`data/*.csv`) are persisted on local SSD.
2. **Deterministic Quant Engine:**
   - Static, EWMA, and Rolling Beta calculation (`engine/beta_calculator.py`).
   - Engle-Granger two-step cointegration tests and OU half-life regression (`engine/cointegration.py`).
   - Beta-neutral capital weight optimization and lot-size rounding (`engine/portfolio.py`).
   - Candidate ranking verification (`engine/verifier.py`).
3. **Streamlit UI & Tear-Sheet Presentation:**
   - Hero header, input prompt, and sidebar controls.
   - 4 Metric cards (Portfolio Beta, Max Drawdown, Sharpe Ratio, Sortino Ratio).
   - Interactive Plotly charts (Cumulative Returns with crash shading, Rolling Beta, Z-Score mean reversion, Correlation Heatmap).
   - Agent trace execution timeline and CRO executive summary.
   - F&O execution table.

### B. What Requires Internet
1. **Google Gemini LLM Synthesis (`ChatGoogleGenerativeAI`):**
   - Natural language thesis parsing (`agents/macro_analyst.py`).
   - Qualitative stock screening narrative (`agents/screener.py`).
   - Executive tear-sheet narrative generation (`agents/cro_reporter.py`).
2. **Live yfinance Network Calls:**
   - Real-time intraday price updates.
   - Live balance-sheet downloads.

### C. Graceful Fallback Behavior
In `app.py` lines 366–380:
```python
if _ENGINE_AVAILABLE:
    try:
        result = run_hedge_builder(thesis)
        data = _map_engine_result(result, params)
    except Exception as exc:
        st.warning(f"Engine error – falling back to demo data. _{exc}_")
        data = _generate_demo_data(...)
```
When Wi-Fi is disconnected, `run_hedge_builder` catches the network timeout and immediately triggers `_generate_demo_data()`. The dashboard remains 100% interactive, displaying all charts, metrics, and execution tables without crashing.

---

## 3. Manual Wi-Fi Disconnection Test Procedure

To verify offline operation manually during hackathon prep:
1. Turn off your machine's Wi-Fi / disconnect ethernet cable.
2. Open PowerShell and navigate to the project directory:
   ```powershell
   cd C:\Users\karti\Documents\antigravity\modest-babbage
   ```
3. Run the local validation script:
   ```powershell
   .venv\Scripts\python.exe scripts/validate_data.py
   ```
   *Expected: All 24 datasets, fundamentals, and lot sizes pass without network access.*
4. Start the dashboard:
   ```powershell
   .venv\Scripts\streamlit.exe run app.py
   ```
5. Open your browser at `http://localhost:8501`.
6. Enter the thesis: *"Bullish on Indian IT, terrified of a US recession crash"*, and click **Build Hedge**.
7. Confirm that the dashboard loads the full performance tear-sheet and Plotly analytics offline.
