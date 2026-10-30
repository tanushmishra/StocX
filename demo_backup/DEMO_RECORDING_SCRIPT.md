# StocX — 60-Second Demo Recording Script

**Recording Shortcut:** `Win + Alt + R` (Windows Xbox Game Bar screen recorder)  
**Target Output Path:** `demo_backup/recordings/stocx_demo_run.mp4`  

---

## 🎬 60-Second Walkthrough Timeline

### [00:00 - 00:08] Application Launch & Header
1. Open PowerShell and run:
   ```powershell
   streamlit run app.py
   ```
2. Press `Win + Alt + R` to begin recording.
3. Bring the browser window (`http://localhost:8501`) into full view.
4. Highlight the hero header:
   > **"🛡️ Market-Neutral Hedge Builder — Autonomous Multi-Agent System | Zero-Hallucination Quant Engine"**

---

### [00:08 - 00:18] Sidebar & Investment Thesis Input
1. Point to the Sidebar settings:
   - Capital: `₹1,000,000`
   - Lookback: `2Y`
   - Stress Regime: `COVID 2020`
2. In the central input box, enter the investment thesis:
   > *"Bullish on Indian IT services, but terrified of a US recession crash"*
3. Click the **🚀 Build Hedge** button.

---

### [00:18 - 00:30] Agent Pipeline Trace & Verification
1. Scroll down to show the spinner and the live **🤖 Agent Pipeline** trace:
   - **MacroParser:** Identifies Sector: IT, Risk: US Recession.
   - **Screener:** Identifies top candidates (`INFY/TCS`, `INFY/WIPRO`, `TCS/TECHM`).
   - **QuantEngine:** Evaluates cointegration and OU half-life (rejects bad pairs).
   - **RiskVerifier:** Confirms Portfolio Beta = 0.01, Max DD reduction > 80%.
   - **CROReporter:** Authorizes F&O execution plan.

---

### [00:30 - 00:45] Before vs. After Metric Cards & Performance Charts
1. Showcase the 4 prominent before/after cards:
   - **Portfolio Beta:** Dropped from `1.12` to `0.01` (-99% market exposure).
   - **Max Drawdown:** Reduced from `-28.4%` to `-4.1%` (Hedge survived crash).
   - **Sharpe Ratio:** Improved from `0.65` to `1.84`.
   - **Sortino Ratio:** Improved from `0.72` to `2.91`.
2. Hover over the interactive **Cumulative Returns** chart to show:
   - Red curve (Unhedged Long) crashing -28% during the shaded COVID window.
   - Green curve (Beta-Neutral Hedged Pair) staying completely flat and market-immune.

---

### [00:45 - 00:55] F&O Lot-Size Execution Plan
1. Scroll to **📦 F&O Lot-Size Execution**:
   - Point out real permitted lot sizes:
     - `INFY.NS`: Long 2 Lots (800 shares @ ₹1,485.50)
     - `TCS.NS`: Short 1 Lot (175 shares @ ₹3,620.75)
   - Show that weights are sized in executable whole derivative contracts.

---

### [00:55 - 01:00] Conclusion & Stop Recording
1. Scroll back up to the hero summary.
2. Press `Win + Alt + R` to stop recording.
3. Move the recorded video from `C:\Users\<user>\Videos\Captures\` to:
   ```text
   demo_backup/recordings/stocx_demo_run.mp4
   ```
