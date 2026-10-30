# 🤖 Multi-Agent Orchestration & Agent System Specification

## 1. Multi-Agent System Overview

The **Market-Neutral Hedge Builder** deploys an autonomous multi-agent architecture orchestrated via **LangGraph**. In accordance with institutional quant practice, the system establishes a strict boundary between qualitative reasoning and mathematical computation.

```
┌────────────────────────────────────────────────────────────────────────┐
│                        LangGraph Orchestrator                          │
│                                                                        │
│   ┌────────────────────────┐         ┌────────────────────────┐       │
│   │   Macro Intent Parser  │────────▶│      Fundamental &     │       │
│   │   (Gemini 2.5 Flash)   │         │    Catalyst Screener   │       │
│   └────────────────────────┘         │   (Gemini 2.5 Flash)   │       │
│                                      └────────────────────────┘       │
│                                                   │                   │
│                                                   ▼                   │
│   ┌────────────────────────┐         ┌────────────────────────┐       │
│   │ Adversarial Verifier   │◀────────│ Quant Execution Engine │       │
│   │   (Gemini 2.5 Pro)     │         │ (Deterministic Python) │       │
│   └────────────────────────┘         └────────────────────────┘       │
│        │               │                                              │
│     REJECT          APPROVE                                           │
│        │               │                                              │
│        ▼               ▼                                              │
│  [Self-Correction   ┌────────────────────────┐                        │
│   Loop to Screener] │  Chief Risk Officer    │                        │
│                     │  (Gemini 2.5 Pro)      │                        │
│                     └────────────────────────┘                        │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Agent 1: Macro Intent Parser Agent

### Role & Objectives
Acts as the **Global Macro Strategist**. It translates unstructured, messy investor prompts into structured quantitative parameters.

* **LLM Engine:** `gemini-2.5-flash`
* **Temperature:** `0.20` (Low temperature for deterministic entity extraction)
* **Output Format:** Pydantic schema via `.with_structured_output(MacroIntent)`

### Structured Pydantic Schema
```python
class MacroIntent(BaseModel):
    target_sector: str = Field(description="NSE sector name (e.g., 'NIFTY IT', 'NIFTY BANK')")
    benchmark: str = Field(default="^NSEI", description="Benchmark ticker (NIFTY 50 = '^NSEI')")
    lookback_days: int = Field(default=252, description="Lookback window in calendar days")
    stress_regime: str = Field(default="COVID_2020", description="Target historical crash regime")
    reasoning: str = Field(description="One-paragraph macro rationale justifying parameter choices")
```

### System Prompt Extract
```
You are a senior macro strategist at an institutional quantitative hedge fund.
Your role is to parse the portfolio manager's natural language thesis into structured parameters:
1. Target Sector: Map to exact NSE sectoral baskets ('NIFTY IT', 'NIFTY BANK', 'NIFTY AUTO', 'NIFTY PHARMA', 'NIFTY PSU BANK').
2. Benchmark: NSE NIFTY 50 benchmark ('^NSEI').
3. Lookback: Default to 252 trading days (1 year) unless otherwise specified.
4. Stress Regime: Select one of 'COVID_2020', '2008_GFC', 'TECH_SELLOFF_2022', or 'ELECTION_2024'.
```

---

## 3. Agent 2: Fundamental & Catalyst Screener Agent

### Role & Objectives
Acts as the **Equity Research Analyst**. It screens all constituents in the target sector to nominate the strongest **Long** candidate and the weakest **Short** candidate.

* **LLM Engine:** `gemini-2.5-flash`
* **Scoring Engine:** Deterministic composite fundamental scoring via `engine.verifier.score_candidate()`
* **Short-Squeeze Guardrail:** Rejects potential short candidates with recent takeover bids or regulatory approvals.
* **Self-Correction Integration:** Reads `state.rejection_log`. Any candidate pair previously rejected by the Risk Verifier is **permanently blacklisted** for subsequent loops.

### Fundamental Composite Scoring Formula
Each constituent stock is evaluated across four normalized financial metrics:

$$\text{Score} = 0.30 \times \text{ROE} + 0.30 \times \text{RevGrowth} + 0.20 \times \left(\frac{1}{\text{PE}}\right) + 0.20 \times \left(\frac{1}{\text{D/E}}\right)$$

* Highest scoring constituent $\to$ Long Candidate (Best boat)
* Lowest scoring constituent $\to$ Short Candidate (Weakest boat)

---

## 4. Node 3: Quant Execution Engine (Deterministic Node)

### Invariant: ZERO LLM INVOCATION
This node is **not an LLM agent**. It is a pure Python functional execution tool wired directly into the LangGraph state graph.

### Pipeline Execution Sequence
1. Fetches daily adjusted close price history via `engine.data_fetcher.fetch_prices()` (with local disk caching in `data_cache/`).
2. Computes daily returns for Long, Short, and Benchmark series.
3. Computes Beta via OLS covariance (`compute_static_beta`) and EWMA covariance (`compute_ewma_beta`).
4. Computes Pearson correlation and Engle-Granger cointegration test (`engle_granger_test`).
5. Solves for beta-neutral position weights ($w_L, w_S$).
6. Calculates spread rolling Z-score and Ornstein-Uhlenbeck half-life ($t_{1/2}$).
7. Simulates full historical backtest and crisis-period stress tests.
8. Converts percentage weights to NSE F&O lot sizes with transaction cost modeling.
9. Writes all computed numbers into `HedgeBuilderState`.

---

## 5. Agent 4: Adversarial Risk Verifier Agent (The Winning Loop)

### Role & Objectives
Acts as the **Institutional Risk Committee Gatekeeper**. It enforces strict quantitative guardrails on the output of the Quant Execution Engine.

* **LLM Engine:** `gemini-2.5-pro` (High-reasoning model for complex risk synthesis)
* **Temperature:** `0.10`

### Deterministic Gate Evaluation
```python
def verify_pair(pair_metrics, unhedged_stats, hedged_stats):
    # Gate 1: Correlation >= 0.65
    # Gate 2: Cointegration p-value < 0.05
    # Gate 3: Hedged MDD < 50% of Unhedged MDD
    # Gate 4: |Realized Beta| < 0.15
    ...
```

### Self-Correction & Routing Logic
```python
def should_continue_or_retry(state: HedgeBuilderState) -> str:
    if state.approved:
        return "cro_reporter"
    elif state.attempt_count < state.max_attempts:
        return "screener"  # Loop back!
    else:
        return "cro_reporter"  # Failure memo after max retries
```

When a pair fails, the Verifier generates a rigorous diagnostic breakdown explaining the statistical failure mode (e.g., "Non-stationary spread indicates structural regime break").

---

## 6. Agent 5: Chief Risk Officer (CRO) Reporter Agent

### Role & Objectives
Acts as the **Chief Risk Officer**. Once a pair is approved (or all attempts are exhausted), this agent composes an institutional investment memo and execution guide.

* **LLM Engine:** `gemini-2.5-pro`
* **Output Format:** High-density Markdown tear-sheet

### Key Sections in the CRO Memo
1. **Executive Thesis Summary:** Overview of the macro driver and selected pair.
2. **Audit Trail of Rejected Pairs:** Transparent log detailing previous candidates that failed verification and why.
3. **Before-vs-After Risk Matrix:** Side-by-side comparison of Unhedged Long vs Beta-Neutral Hedged portfolio.
4. **Crisis Stress Test Breakdown:** Performance narrative during the designated black swan regime.
5. **NSE F&O Execution Plan:** Lot allocations, margin capital requirements, and friction impact.

---

## 7. Complete Rejection & Self-Correction Trace Walkthrough

Below is an actual runtime trace demonstrating how the multi-agent system self-corrects:

```
[00:01] MacroParser     ▸ Extracted: Sector="NIFTY IT", Benchmark="^NSEI", Stress="COVID_2020"
[00:02] Screener        ▸ Attempt 1: Evaluating NIFTY IT constituents.
                          Top Long: TCS.NS (Score: 0.88), Worst Short: TECHM.NS (Score: 0.32)
                          Nominated Pair: Long TCS.NS / Short TECHM.NS
[00:03] QuantEngine     ▸ Fetching prices. Calculating covariance and Engle-Granger test...
                          Correlation: 0.74, Cointegration p-value: 0.182 (Critical: 0.05)
[00:04] RiskVerifier    ▸ REJECTED ❌ (Attempt 1/5)
                          Gate 'cointegration' failed: p-value 0.182 >= 0.05 (non-stationary spread).
                          Logging failure to state.rejection_log. Routing to Screener.
[00:05] Screener        ▸ Attempt 2: Excluding blacklisted pair [TCS.NS, TECHM.NS].
                          Top Long: TCS.NS (Score: 0.88), Next Short: WIPRO.NS (Score: 0.41)
                          Nominated Pair: Long TCS.NS / Short WIPRO.NS
[00:06] QuantEngine     ▸ Computing metrics for TCS.NS / WIPRO.NS...
                          Correlation: 0.84, Cointegration p-value: 0.012, Realized Beta: 0.02
[00:07] RiskVerifier    ▸ APPROVED ✅ (Attempt 2/5)
                          All 4 gates passed. Routing to CRO Reporter.
[00:09] CROReporter     ▸ Generating institutional tear-sheet memo. Execution plan finalized.
```
